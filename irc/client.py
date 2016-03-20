# -*- coding: utf-8 -*-
from __future__ import absolute_import, division

'''
Internet Relay Chat (IRC) protocol client library.

Copyright © 1999-2002 Joel Rosdahl
Copyright © 2011-2016 Jason R. Coombs
Copyright © 2009 Ferry Boender
Copyright © 2016 Jonas Thiem

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
'''


"""
This library is intended to encapsulate the IRC protocol in Python.
It provides an event-driven IRC client framework.  It has
a fairly thorough support for the basic IRC protocol, CTCP, and DCC chat.

To best understand how to make an IRC client, the reader more
or less must understand the IRC specifications.  They are available
here: [IRC specifications].

The main features of the IRC client framework are:

  * Abstraction of the IRC protocol.
  * Handles multiple simultaneous IRC server connections.
  * Handles server PONGing transparently.
  * Messages to the IRC server are done by calling methods on an IRC
    connection object.
  * Messages from an IRC server triggers events, which can be caught
    by event handlers.
  * Reading from and writing to IRC server sockets are normally done
    by an internal select() loop, but the select()ing may be done by
    an external main loop.
  * Functions can be registered to execute at specified times by the
    event-loop.
  * Decodes CTCP tagging correctly (hopefully); I haven't seen any
    other IRC client implementation that handles the CTCP
    specification subtilties.
  * A kind of simple, single-server, object-oriented IRC client class
    that dispatches events to instance methods is included.

Current limitations:

  * Data is not written asynchronously to the server, i.e. the write()
    may block if the TCP buffers are stuffed.
  * DCC file transfers are not supported.
  * RFCs 2810, 2811, 2812, and 2813 have not been considered.

Notes:
  * connection.quit() only sends QUIT to the server.
  * ERROR from the server triggers the error event and the disconnect event.
  * dropping of the connection triggers the disconnect event.


.. [IRC specifications] http://www.irchelp.org/irchelp/rfc/
"""

import bisect
import re
import select
import socket
import time
import struct
import logging
import threading
import abc
import collections
import functools
import itertools
import contextlib
import time
import six
from jaraco.functools import Throttler
try:
    import queue
except ImportError:
    import Queue as queue

try:
    import pkg_resources
except ImportError:
    pass

from . import connection
from . import events
from . import functools as irc_functools
from . import buffer
from . import schedule
from . import features
from . import ctcp
from . import message

log = logging.getLogger(__name__)

# Set the version tuple
try:
    VERSION_STRING = pkg_resources.require('irc')[0].version
    VERSION = tuple(int(res) for res in re.findall('\d+', VERSION_STRING))
except Exception:
    VERSION_STRING = 'unknown'
    VERSION = ()


class IRCError(Exception):
    "An IRC exception"

class InvalidCharacters(ValueError):
    "Invalid characters were encountered in the message"

class MessageTooLong(ValueError):
    "Message is too long"

class PrioritizedHandler(
        collections.namedtuple('Base', ('priority', 'callback'))):
    def __lt__(self, other):
        "when sorting prioritized handlers, only use the priority"
        return self.priority < other.priority

class Client(object):
    """
    Processes events from one or more IRC server connections.

    The methods of most interest for an IRC client writer are:

       - add_server (connect to a new server)

       - add_global_handler, remove_global_handler (events)

    Here is a simple code example:

    ```
        client = irc.client.Client()
        client.add_global_handler("welcome",
            lambda connection, event: connection.privmsg("a_nickname",
                "Hi there!")
        ) # do this before add_server to ensure it's triggered
        client.add_server("irc.some.where", 6667, "my_own_nickname")
        while True:
            client.process(max_wait=1.0)
    ```

    This will connect to the IRC server irc.some.where on port 6667
    using the nickname my_own_nickname and send the message "Hi there!"
    to the nickname a_nickname.

    The methods of this class are thread-safe; accesses to and modifications
    of its internal data is guarded by a mutex.
    """

    def __do_nothing(*args, **kwargs):
        pass

    def __init__(self, on_connect=__do_nothing, on_disconnect=__do_nothing):
        """
        Constructor for a multi connections client.

        on_connect(server_connection):
            An optional callback invoked when a new connection is made.
            The ServerConnection instance will be passed as a parameter.

        on_disconnect(server_connection):
            An optional callback invoked when a new connection is stopped.
            The ServerConnection instance will be passed as a parameter.

        """

        self._on_connect = on_connect
        self._on_disconnect = on_disconnect

        self.connections = []
        self.handlers = {}
        # Modifications to these shared lists and dict need to be thread-safe
        self.mutex = threading.RLock()
        self.event_handling_mutex = threading.Lock()
        self.event_handling_queue = queue.Queue()

        self.add_global_handler("ping", _ping_ponger, -42)

    def add_server(self, server, port, nickname, password=None, username=None,
            ircname=None, connect_factory=connection.Factory()):
        """
        Add a connection to a new server.
        Arguments:

        * server - Server name
        * port - Port number
        * nickname - The nickname
        * password - Password (if any)
        * username - The username
        * ircname - The IRC name ("realname")
        * server_address - The remote host/port of the server
        * connect_factory - A callable that takes the server address and
          returns a connection (with a socket interface)

        Internally creates and stores a ServerConnection instance.
        You'll get it passed during on_connect / on_disconnect events (see
        the documentation for __init__).
        """

        c = ServerConnection(self, server, port, nickname=nickname,
            password=password, username=username, ircname=ircname,
            connect_factory=connect_factory)
        with self.mutex:
            self.connections.append(c)
        c.start()
        return c

    def disconnect_all(self, message=""):
        """ Disconnects all connections. """
        with self.mutex:
            for c in self.connections:
                c.disconnect(message)

    def add_global_handler(self, event, handler, priority=0):
        """
        Adds a global handler function for a specific event type.

        Arguments:

            event -- Event type (a string).  Check the values of
                     numeric_events for possible event types.

            handler -- Callback function taking 'connection' and 'event'
                       parameters.

            priority -- A number (the lower number, the higher priority).

        The handler function is called whenever the specified event is
        triggered in any of the connections.  See documentation for
        the Event class.

        The handler functions are called in priority order (lowest
        number is highest priority).  If a handler function returns
        False, no more handlers will be called.
        """
        handler = PrioritizedHandler(priority, handler)
        with self.mutex:
            event_handlers = self.handlers.setdefault(event, [])
            bisect.insort(event_handlers, handler)

    def remove_global_handler(self, event, handler):
        """Removes a global handler function.

        Arguments:

            event -- Event type (a string).
            handler -- Callback function.

        Returns 1 on success, otherwise 0.
        """
        with self.mutex:
            if not event in self.handlers:
                return 0
            for h in self.handlers[event]:
                if handler == h.callback:
                    self.handlers[event].remove(h)
        return 1

    def dcc(self, dcctype="chat"):
        """
        Creates and returns a DCCConnection object.

        Arguments:

            dcctype -- "chat" for DCC CHAT connections or "raw" for
                       DCC SEND (or other DCC types). If "chat",
                       incoming data will be split in newline-separated
                       chunks. If "raw", incoming data is not touched.
        """
        with self.mutex:
            c = DCCConnection(self, dcctype)
            self.connections.append(c)
        return c

    def _handle_event(self, connection, event):
        """
        Handle an Event event incoming on ServerConnection connection.
        """
        with self.event_handling_mutex:
            handlers_to_be_called = []
            with self.mutex:
                h = self.handlers
                matching_handlers = sorted(
                    h.get("all_events", []) +
                    h.get(event.type, [])
                )
                for handler in matching_handlers:
                    handlers_to_be_called.append(handler)
            self.event_handling_queue.put((connection, event,
                handlers_to_be_called))

    def process(self, max_wait=0):
        """
        Trigger scheduled events inside your main application loop/thread.
        """
        event_info = None

        # Wait for item in event queue up to specified wait time:
        try:
            event_info = self.event_handling_queue.get(True,
                timeout=max_wait)
        except queue.Empty:
            pass
        while event_info != None:
            # Trigger the event handlers:
            for handler in event_info[2]:
                result = handler.callback(event_info[0], event_info[1])
                if result is False:
                    return
            # Also get all other events that are to be handled right now:
            try:
                event_info = self.event_handling_queue.get(False)
            except queue.Empty:
                return

    def _remove_connection(self, connection):
        """[Internal]"""
        with self.mutex:
            self.connections.remove(connection)
            self._on_disconnect(connection.socket)

_cmd_pat = "^(@(?P<tags>[^ ]*) )?(:(?P<prefix>[^ ]+) +)?(?P<command>[^ ]+)( *(?P<argument> .+))?"
_rfc_1459_command_regexp = re.compile(_cmd_pat)


class ServerConnectionError(IRCError):
    pass

class ServerNotConnectedError(ServerConnectionError):
    pass


class ServerConnection(threading.Thread):
    """
    An IRC server connection.

    ServerConnection objects are instantiated by calling the server
    method on a Reactor object.
    """

    class Channel(object):
        def __init__(self, name):
            self.name = name
            self.users = None
            self.topic = None
            self._names_response_temporary = []
            self.delayed_join_event = None
            self.delayed_join_event_time = time.monotonic()

        def _should_trigger_delayed_join_event(self):
            if self.delayed_join_event == None:
                return False
            if (self.topic != None and self.users != None) or \
                    self.delayed_join_event_time + 20 < time.monotonic():
                return True
            return False

    def __init__(self, owning_client, server, port, nickname,
            password=None, username=None, ircname=None,
            connect_factory=connection.Factory()):
        super(ServerConnection, self).__init__()
        self._connected = False
        self.features = features.FeatureSet()
        self.client = owning_client

        self._welcome_event_triggered = False
        self.socket = None
        self.server = server
        self.port = port
        self.nickname_on_connect = nickname
        self.username = username or nickname
        self.password = password
        self.ircname = ircname or nickname
        self.connect_factory = connect_factory
        self._channels = dict()

        self.mutex = threading.Lock()

    def run(self):
        self._do_connect()
        while True:
            with self.mutex:
                if self.socket != None:
                    if self._check_if_data_available(self.socket,
                            timeout=0.2):
                        self.process_data()
                    # If 001 / RPL_WELCOME was delayed and this server sent
                    # no 005 / RPL_ISUPPORT due to being old, allow the
                    # delayed event to be triggered after some time after 004
                    if self.delayed_001 and self.delayed_001_saw_004:
                        if self.delayed_001_time + 10 < time.monotonic():
                            log.debug("001 DELAY: emitting delayed " +\
                                "welcome event now. [005 timeout]")
                            self._welcome_event_triggered = True
                            self._handle_event(self.delayed_001_event)
                            self.delayed_001 = False

    @property
    def ready(self):
        with self.mutex:
            return (self.connected and self._welcome_event_triggered)

    def _do_connect(self):
        with self.mutex:
            self._welcome_event_triggered = False
            with self.client.mutex:
                # (Re-)set information for delayed "welcome" / 001 event:
                self.delayed_001 = False
                self.delayed_001_event = None
                self.delayed_001_time = 0
                self.delayed_001_saw_004 = False

                log.debug("connect(server=%r, port=%r, nickname=%r, ...)",
                    self.server, self.port, self.nickname_on_connect)

                if self.connected:
                    self.disconnect("Changing servers")
                else:
                    self.disconnect(
                        "Ensure we are disconnected before reconnecting")

                self.buffer = b""
                self.handlers = {}
                self.real_server_name = ""
                self.real_nickname = self.nickname_on_connect
                self.server_address = (self.server, self.port)
                try:
                    self.socket = self.connect_factory(self.server_address)
                except socket.error as ex:
                    raise ServerConnectionError(
                        "Couldn't connect to socket: %s" % ex)
                self._connected = True

            threading.Thread(target=self.client._on_connect).start()

            # Log on...
            if self.password:
                self.pass_(self.password)
            self.nick(self.nickname_on_connect)
            self.user(self.username, self.ircname)

    def reconnect(self):
        """
        Reconnect to the server.
        """
        self._do_connect()

    def close(self):
        """
        Close the connection.

        This method closes the connection permanently; after it has
        been called, the object is unusable.
        """
        # Without this thread lock, there is a window during which
        # select() can find a closed socket, leading to an EBADF error.
        with self.mutex:
            with self.client.mutex:
                self.disconnect("Closing object")
                self.client._remove_connection(self)

    @property
    def server_name(self):
        """
        Get the (real) server name.

        This method returns the (real) server name, or, more
        specifically, what the server calls itself.
        """
        return self.real_server_name or ""

    @property
    def nickname(self):
        """
        The current nickname you have on this connection.

        Depending on whether the desired nickname on connect was taken or on
        whether the server has done any forced renames, this might differ
        from the original nickname choice.
        """
        return self.real_nickname

    @property
    def channels(self):
        """
        All the channels on this server you are currently in.

        Being in a channel is usually required to see all the users in it, to
        read all the messages in there and to be able to send messages to
        participate in a conversation.
        To join an additional channel or leave one, use join()/part().
        Please note join()/part() is not instant.
        """
        channel_list = []
        with self.mutex:
            for chan in self._channels.keys():
                if self._channels[chan].delayed_join_event != None:
                    continue
                channel_list.append(self._channels[chan].name)
        return channel_list

    def get_channel_users(self, channel):
        """
        The nicknames of all the users that are inside a channel you are
        currently in (including yourself).

        This will throw a ValueError if not currently in this channel.
        Please note .join() will not be instant and you need to wait for
        the "join" event before you can use this.
        """
        try:
            users = self._channels[channel.lower()].users
        except KeyError:
            raise ValueError("not currently in channel " + str(channel) +\
                " - did you wait for the \"join\" event after using .join()?")
        if users == None:
            users = []
        return users

    def get_channel_topic(self, channel):
        """
        Get the current topic of the specified channel.

        This will throw a ValueError if not currently in this channel.
        """
        try:
            topic = self._channels[channel.lower()].topic
        except KeyError:
            raise ValueError("not currently in channel " + str(channel) +\
                " - did you wait for the \"join\" event after using .join()?")
        return (topic or "")

    @staticmethod
    def _check_if_data_available(socket, timeout=0):
        socket_list = [socket]

        # Check whether socket is in read event list:
        read_sockets, write_sockets, error_sockets = select.select(
            socket_list , [], [], timeout)
        if socket in read_sockets:
            # It is. -> data available (or disconnect event)
            return True
        return False

    def process_data(self):
        """"
        Internal!

        Read and process input from self.socket.
        """

        # Read bytes until we got a line or a full buffer:
        while len(self.buffer) < 600 and self.buffer.find(b"\n") < 0:
            try:
                reader = getattr(self.socket, 'read', self.socket.recv)
                new_data = reader(1)
            except socket.error:
                # The server hung up.
                self.disconnect("Connection reset by peer")
                return
            if not new_data:
                # Read nothing: connection must be down.
                self.disconnect("Connection reset by peer")
                return

            self.buffer += new_data

            # If no further data can be read without blocking, abort:
            if not self._check_if_data_available(self.socket):
                break

        # If we got no line, the server is violating the protocol:
        if self.buffer.find(b"\n") < 0:
            self.buffer = b""
            return

        # Process each non-empty line:
        next_break = self.buffer.find(b"\n")
        while next_break >= 0:
            next_line = self.buffer[:next_break]
            self.buffer = self.buffer[next_break+1:]
            if next_line.endswith(b"\r"):
                next_line = next_line[:-1]
            log.debug("FROM SERVER: %s", next_line)

            # Decode preferrably with utf-8:
            decoded_line = None
            try:
                decoded_line = next_line.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    decoded_line = next_line.decode("latin-1")
                except Exception as e:
                    decoded_line = next_line.decode("utf-8", "replace")

            # Process line if not empty:
            if len(decoded_line) > 0:
                self._process_line(decoded_line)

            # Advance to next line:
            next_break = self.buffer.find(b"\n")

    def _process_line(self, line):
        event = Event("all_raw_messages", self.server_name, None,
            [line])
        self._handle_event(event)

        grp = _rfc_1459_command_regexp.match(line).group

        source = NickMask.from_group(grp("prefix"))
        command = self._command_from_group(grp("command"))
        arguments = message.Arguments.from_group(grp('argument'))
        tags = message.Tag.from_group(grp('tags'))

        if source and not self.real_server_name:
            self.real_server_name = source

        # Helper function to trigger delayed JOIN event for a channel:
        def trigger_delayed_join(channel, force=False):
            try:
                if self._channels[channel].delayed_join_event == None:
                    return
                if self._channels[channel].\
                        _should_trigger_delayed_join_event() or force:
                    ev = self._channels[channel].delayed_join_event
                    self._channels[channel].delayed_join_event = None
                    self._handle_event(ev)
            except KeyError:
                pass

        # Special handling of events for internal use:
        if command == "nick" and len(arguments) >= 1:
            if source.nick.lower() == self.real_nickname.lower():
                # Handle ourselves renaming:
                self.real_nickname = arguments[0]
            else:
                # Update channel user lists for someone else renaming:
                for channel in self._channels:
                    # Rename nick in known users list:
                    if channel.users != None:
                        index = 0
                        for user in channel.users:
                            if user.lower() == source.nick.lower():
                                del(channel.users[index])
                                channel.users.append(arguments[0])
                                break
                            index += 1
                    # Rename nick in currently being transmitted NAMES list:
                    index = 0
                    for user in channel._names_response_temporary:
                        if user.lower() == source.nick.lower():
                            del(channel._names_response_temporary[index])
                            channel._names_response_temporary.append(
                                arguments[0])
                            break
                        index += 1
        elif command == "welcome":
            # Record the nickname in case the client changed nick
            # in a nicknameinuse callback.
            self.real_nickname = arguments[0]
        elif command == "featurelist":
            self.features.load(arguments)
        elif command == "join" and len(arguments) >= 1:
            if source.partition("!")[0].lower() == self.real_nickname.lower():
                # Handle ourselves joining a new channel:
                self._channels[arguments[0].lower()] = self.Channel(
                    arguments[0])
            else:
                # Update channel user lists for someone else joining:
                try:
                    if self.channels[arguments[0].lower()].users != None:
                        self.channels[arguments[0].lower()].users.append(
                            source.partition("!")[0])
                except KeyError:
                    pass
        elif command == "part" and len(arguments) >= 1:
            if source.partition("!")[0].lower() == self.real_nickname.lower():
                # Handle ourselves leaving a channel:
                try:
                    del(self._channels[arguments[0].lower()])
                except KeyError:
                    pass
            else:
                # Update channel user lists for someone else leaving:
                try:
                    if self.channels[arguments[0].lower()].users != None:
                        index = 0
                        for user in \
                                self._channels[arguments[0].lower()].users:
                            if user.lower() == \
                                    source.partition("!")[0].lower():
                                del(self._channels[arguments[0].lower()].\
                                    users[index])
                                break
                            index += 1
                except KeyError:
                    pass
        elif command == "kick" and len(arguments) >= 2:
            if arguments[1].lower() == self.real_nickname.lower():
                # Handle ourselves getting kicked from the channel:
                try:
                    del(self._channels[arguments[0].lower()])
                except KeyError:
                    pass
            else:
                # Update channel user lists for someone else getting kicked:
                try: 
                    if self.channels[arguments[0].lower()].users != None:
                        index = 0
                        for user in \
                                self._channels[arguments[0].lower()].users:
                            if user.lower() == arguments[0].lower():
                                del(self._channels[arguments[0].lower()].\
                                    users[index])
                                break
                            index += 1
                except KeyError:
                    pass
        elif command == "quit":
            if arguments[0].lower() != self.real_nickname.lower():
                # Update channel user lists for someone else quitting:
                for channel in self._channels:
                    if channel.name.users != None:
                        index = 0
                        for user in channel.name.users:
                            if user.lower() ==\
                                    source.partition("!")[0].lower():
                                del(channel.name.users[index])
                                break
                            index += 1
        elif command == "kill":
            if arguments[0].lower() != self.real_nickname.lower():
                # Update channel user lists for someone else getting killed:
                for channel in self._channels:
                    if channel.name.users != None:
                        index = 0
                        for user in channel.name.users:
                            if user.lower() == arguments[0].lower():
                                del(channel.name.users[index])
                                break
                            index += 1
        elif command == "namreply" and len(arguments) >= 4:
            try:
                def remove_prefix(nick):
                    # This is intentionally written to strip multiple prefixes
                    # for IRCv3 multi-prefix support.
                    removed = True
                    while removed:
                        removed = False
                        for prefix in self.features.prefix:
                            if nick.startswith(prefix):
                                nick = nick[1:]
                                removed = True
                    return nick
                self._channels[arguments[2].lower()].\
                    _names_response_temporary += [\
                    remove_prefix(nick) for nick in arguments[3].split(" ")]
            except KeyError:
                pass
        elif command == "currenttopic" and len(arguments) >= 3:
            try:
                # Set channel topic:
                self._channels[arguments[1].lower()].topic = arguments[2]

                # Trigger delayed join if required:
                trigger_delayed_join(arguments[1].lower())
            except KeyError:
                pass
        elif command == "endofnames" and len(arguments) >= 2:
            try:
                # Set updated channel user list:
                self._channels[arguments[1].lower()].users = \
                    self._channels[arguments[1].lower()].\
                        _names_response_temporary
                self._channels[arguments[1].lower()].\
                    _names_response_temporary = []

                # Trigger delayed join if required:
                trigger_delayed_join(arguments[1].lower())
            except KeyError:
                pass
        elif (command == "privmsg" or command == "notice" or \
                command == "join" or command == "part" or \
                command == "kick" or command == "mode" or \
                command == "topic" or command == "notice") \
                and len(arguments) >= 0:
            # Force delayed JOIN event if not happened yet:
            trigger_delayed_join(arguments[0].lower(), force=True)

        # Trigger user callbacks:
        handler = (
            self._handle_message
            if command in ["privmsg", "notice"]
            else self._handle_other
        )
        handler(arguments, command, source, tags)

    def _handle_message(self, arguments, command, source, tags):
        target, msg = arguments[:2]
        messages = ctcp.dequote(msg)
        if command == "privmsg":
            if is_channel(target):
                command = "pubmsg"
        else:
            if is_channel(target):
                command = "pubnotice"
            else:
                command = "privnotice"
        for m in messages:
            if isinstance(m, tuple):
                if command in ["privmsg", "pubmsg"]:
                    command = "ctcp"
                else:
                    command = "ctcpreply"

                m = list(m)
                log.debug("command: %s, source: %s, target: %s, "
                          "arguments: %s, tags: %s", command, source, target, m, tags)
                event = Event(command, source, target, m, tags)
                self._handle_event(event)
                if command == "ctcp" and m[0] == "ACTION":
                    event = Event("action", source, target, m[1:], tags)
                    self._handle_event(event)
            else:
                log.debug("command: %s, source: %s, target: %s, "
                          "arguments: %s, tags: %s", command, source, target, [m], tags)
                event = Event(command, source, target, [m], tags)
                self._handle_event(event)

    def _handle_other(self, arguments, command, source, tags):
        target = None
        if command == "quit":
            arguments = [arguments[0]]
        elif command == "ping":
            target = arguments[0]
        else:
            target = arguments[0] if arguments else None
            arguments = arguments[1:]
        if command == "mode":
            if not is_channel(target):
                command = "umode"
        log.debug("command: %s, source: %s, target: %s, "
                  "arguments: %s, tags: %s", command, source, target, arguments, tags)
        event = Event(command, source, target, arguments, tags)

        # Delay 001 / RPL_WELCOME event:
        if command == "welcome" and not self.delayed_001:
            self.delayed_001 = True
            self.delayed_001_event = event
            self.delayed_001_time = time.monotonic()
            log.debug("001 DELAY: welcome event delayed.")
            return
        # Delay JOIN events for topic / names info:
        elif command == "join" and target != None:
            try:
                self._channels[target].delayed_join_event =\
                    event
                return
            except KeyError:
                pass

        self._handle_event(event)

        # If getting 005 / RPL_ISUPPORT, emit delayed 001 if we delayed it:
        if command == "featurelist":
            if self.delayed_001:
                log.debug("001 DELAY: emitting delayed welcome " +\
                    "event now. [005 received]")
                self._handle_event(self.delayed_001_event)
                self._welcome_event_triggered = True
                self.delayed_001 = False
        # .. otherwise, if we get a 004 / RPL_MYINFO, schedule a 001 emit:
        elif command == "myinfo" and self.delayed_001:
            self.delayed_001_saw_004 = True

    @staticmethod
    def _command_from_group(group):
        command = group.lower()
        # Translate numerics into more readable strings.
        return events.numeric.get(command, command)

    def _handle_event(self, event):
        """ [Internal] """
        self.client._handle_event(self, event)
        if event.type in self.handlers:
            for fn in self.handlers[event.type]:
                fn(self, event)

    @property
    def connected(self):
        """ Return connection status.

        Returns true if connected, otherwise false.
        """
        return self._connected

    def add_global_handler(self, *args):
        """ Add global handler.

        See documentation for IRC.add_global_handler.
        """
        self.client.add_global_handler(*args)

    def remove_global_handler(self, *args):
        """ Remove global handler.

        See documentation for IRC.remove_global_handler.
        """
        self.client.remove_global_handler(*args)

    def action(self, target, action):
        """ Send a CTCP ACTION command. """
        self.ctcp("ACTION", target, action)

    def admin(self, server=""):
        """ Send an ADMIN command. """
        self.send_raw(" ".join(["ADMIN", server]).strip())

    def cap(self, subcommand, *args):
        """
        Send a CAP command according to `the spec
        <http://ircv3.atheme.org/specification/capability-negotiation-3.1>`_.

        Arguments:

            subcommand -- LS, LIST, REQ, ACK, CLEAR, END
            args -- capabilities, if required for given subcommand

        Example:

            .cap('LS')
            .cap('REQ', 'multi-prefix', 'sasl')
            .cap('END')
        """
        cap_subcommands = set('LS LIST REQ ACK NAK CLEAR END'.split())
        client_subcommands = set(cap_subcommands) - set('NAK')
        assert subcommand in client_subcommands, "invalid subcommand"

        def _multi_parameter(args):
            """
            According to the spec::

                If more than one capability is named, the RFC1459 designated
                sentinel (:) for a multi-parameter argument must be present.

            It's not obvious where the sentinel should be present or if it
            must be omitted for a single parameter, so follow convention and
            only include the sentinel prefixed to the first parameter if more
            than one parameter is present.
            """
            if len(args) > 1:
                return (':' + args[0],) + args[1:]
            return args

        args = _multi_parameter(args)
        self.send_raw(' '.join(('CAP', subcommand) + args))

    def ctcp(self, ctcptype, target, parameter=""):
        """ Send a CTCP command. """
        ctcptype = ctcptype.upper()
        tmpl = (
            "\001{ctcptype} {parameter}\001" if parameter else
            "\001{ctcptype}\001"
        )
        self.privmsg(target, tmpl.format(**vars()))

    def ctcp_reply(self, target, parameter):
        """Send a CTCP REPLY command."""
        self.notice(target, "\001%s\001" % parameter)

    def disconnect(self, message=""):
        """ Hang up the connection.

        Arguments:

            message -- Quit message.
        """
        if not self.connected:
            if self.socket != None:
                try:
                    self.socket.close()
                except socket.error:
                    pass
                self.socket = None
            return

        self._connected = False

        self.quit(message)

        try:
            self.socket.shutdown(socket.SHUT_WR)
            self.socket.close()
        except socket.error:
            pass
        self.socket = None
        self._handle_event(Event("disconnect", self.server, "", [message]))

    def globops(self, text):
        """ Send a GLOBOPS command. """
        self.send_raw("GLOBOPS :" + text)

    def info(self, server=""):
        """ Send an INFO command. """
        self.send_raw(" ".join(["INFO", server]).strip())

    def invite(self, nick, channel):
        """ Send an INVITE command. """
        self.send_raw(" ".join(["INVITE", nick, channel]).strip())

    def ison(self, nicks):
        """ Send an ISON command.

        Arguments:

            nicks -- List of nicks.
        """
        self.send_raw("ISON " + " ".join(nicks))

    def join(self, channel, key=""):
        """ Send a JOIN command.
        Please note this command will not be instant. Subscribe with the
        owning client's .add_global_handler() to the "join" event to find out
        about completed channel joins.
        """
        self.send_raw("JOIN %s%s" % (channel, (key and (" " + key))))

    def kick(self, channel, nick, comment=""):
        """ Send a KICK command. """
        tmpl = "KICK {channel} {nick}"
        if comment:
            tmpl += " :{comment}"
        self.send_raw(tmpl.format(**vars()))

    def links(self, remote_server="", server_mask=""):
        """ Send a LINKS command. """
        command = "LINKS"
        if remote_server:
            command = command + " " + remote_server
        if server_mask:
            command = command + " " + server_mask
        self.send_raw(command)

    def list(self, channels=None, server=""):
        """ Send a LIST command. """
        command = "LIST"
        if channels != None:
            channels = ",".join(channels)
            command += ' ' + channels
        if server:
            command = command + " " + server
        self.send_raw(command)

    def lusers(self, server=""):
        """ Send a LUSERS command."""
        self.send_raw("LUSERS" + (server and (" " + server)))

    def mode(self, target, command):
        """ Send a MODE command."""
        self.send_raw("MODE %s %s" % (target, command))

    def motd(self, server=""):
        """ Send an MOTD command."""
        self.send_raw("MOTD" + (server and (" " + server)))

    def names(self, channels=None):
        """ Send a NAMES command."""
        tmpl = "NAMES {channels}" if channels else "NAMES"
        if channels != None:
            if isinstance(channels, str) or isintance(channels,
                    basestring):
                channels = [ channels ]
            channels = ','.join(channels)
        self.send_raw(tmpl.format(channels=channels))

    def nick(self, newnick):
        """ Send a NICK command."""
        self.send_raw("NICK " + newnick)

    def notice(self, target, text):
        """ Send a NOTICE command."""
        # Should limit len(text) here!
        self.send_raw("NOTICE %s :%s" % (target, text))

    def oper(self, nick, password):
        """ Send an OPER command."""
        self.send_raw("OPER %s %s" % (nick, password))

    def part(self, channels, message=""):
        """ Send a PART command.
        Please note this command will not be instant. Subscribe with the
        owning client's .add_global_handler() to the "part" event to find out
        about completed channel parts.
        """
        if isinstance(channels, str) or isintance(channels,
                basestring):
            channels = [ channels ]
        cmd_parts = [
            'PART',
            ','.join(channels),
        ]
        if message: cmd_parts.append(message)
        self.send_raw(' '.join(cmd_parts))

    def pass_(self, password):
        """ Send a PASS command."""
        self.send_raw("PASS " + password)

    def ping(self, target, target2=""):
        """ Send a PING command."""
        self.send_raw("PING %s%s" % (target, target2 and (" " + target2)))

    def pong(self, target, target2=""):
        """ Send a PONG command."""
        self.send_raw("PONG %s%s" % (target, target2 and (" " + target2)))

    def privmsg(self, target, text):
        """ Send a PRIVMSG command."""
        self.send_raw("PRIVMSG %s :%s" % (target, text))

    def privmsg_many(self, targets, text):
        """ Send a PRIVMSG command to multiple targets. """
        target = ','.join(targets)
        return self.privmsg(target, text)

    def quit(self, message=""):
        """ Send a QUIT command. """
        # Note that many IRC servers don't use your QUIT message
        # unless you've been connected for at least 5 minutes!
        self.send_raw("QUIT" + (message and (" :" + message)))

    def _prep_message(self, string):
        # The string should not contain any carriage return other than the
        # one added here.
        if '\n' in string:
            msg = "Carriage returns not allowed in privmsg(text)"
            raise InvalidCharacters(msg)
        bytes = string.encode('utf-8') + b'\r\n'
        # According to the RFC http://tools.ietf.org/html/rfc2812#page-6,
        # clients should not transmit more than 512 bytes.
        if len(bytes) > 512:
            msg = "Messages limited to 512 bytes including CR/LF"
            raise MessageTooLong(msg)
        return bytes

    def send_raw(self, string):
        """ Send raw string to the server.

        The string will be padded with appropriate CR LF.
        """
        if self.socket is None:
            raise ServerNotConnectedError("Not connected.")
        sender = getattr(self.socket, 'write', self.socket.send)
        try:
            sender(self._prep_message(string))
            log.debug("TO SERVER: %s", string)
        except socket.error:
            # Ouch!
            self.disconnect("Connection reset by peer.")

    def squit(self, server, comment=""):
        """Send an SQUIT command."""
        self.send_raw("SQUIT %s%s" % (server, comment and (" :" + comment)))

    def stats(self, statstype, server=""):
        """Send a STATS command."""
        self.send_raw("STATS %s%s" % (statstype, server and (" " + server)))

    def time(self, server=""):
        """Send a TIME command."""
        self.send_raw("TIME" + (server and (" " + server)))

    def topic(self, channel, new_topic=None):
        """Send a TOPIC command."""
        if new_topic is None:
            self.send_raw("TOPIC " + channel)
        else:
            self.send_raw("TOPIC %s :%s" % (channel, new_topic))

    def trace(self, target=""):
        """Send a TRACE command."""
        self.send_raw("TRACE" + (target and (" " + target)))

    def user(self, username, realname):
        """Send a USER command."""
        self.send_raw("USER %s 0 * :%s" % (username, realname))

    def userhost(self, nicks):
        """Send a USERHOST command."""
        self.send_raw("USERHOST " + ",".join(nicks))

    def users(self, server=""):
        """Send a USERS command."""
        self.send_raw("USERS" + (server and (" " + server)))

    def version(self, server=""):
        """Send a VERSION command."""
        self.send_raw("VERSION" + (server and (" " + server)))

    def wallops(self, text):
        """Send a WALLOPS command."""
        self.send_raw("WALLOPS :" + text)

    def who(self, target="", op=""):
        """Send a WHO command."""
        self.send_raw("WHO%s%s" % (target and (" " + target), op and (" o")))

    def whois(self, targets):
        """Send a WHOIS command."""
        if isinstance(targets, str) or isintance(targets,
                basestring):
            targets = [ targets ]
        self.send_raw("WHOIS " + ",".join(targets))

    def whowas(self, nick, max="", server=""):
        """Send a WHOWAS command."""
        self.send_raw("WHOWAS %s%s%s" % (nick,
                                         max and (" " + max),
                                         server and (" " + server)))

    def set_rate_limit(self, frequency):
        """
        Set a `frequency` limit (messages per second) for this connection.
        Any attempts to send faster than this rate will block.
        """
        self.send_raw = Throttler(self.send_raw, frequency)

    def set_keepalive(self, interval):
        """
        Set a keepalive to occur every ``interval`` on this connection.
        """
        pinger = functools.partial(self.ping, 'keep-alive')
        self.reactor.execute_every(period=interval, function=pinger)


class DCCConnectionError(IRCError):
    pass


class DCCConnection(object):
    """
    A DCC (Direct Client Connection).

    DCCConnection objects are instantiated by calling the dcc
    method on a Reactor object.
    """

    def __init__(self, reactor, dcctype):
        super(DCCConnection, self).__init__(reactor)
        self.connected = 0
        self.passive = 0
        self.dcctype = dcctype
        self.peeraddress = None
        self.peerport = None
        self.socket = None

    def connect(self, address, port):
        """Connect/reconnect to a DCC peer.

        Arguments:
            address -- Host/IP address of the peer.

            port -- The port number to connect to.

        Returns the DCCConnection object.
        """
        self.peeraddress = socket.gethostbyname(address)
        self.peerport = port
        self.buffer = buffer.LineBuffer()
        self.handlers = {}
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.passive = 0
        try:
            self.socket.connect((self.peeraddress, self.peerport))
        except socket.error as x:
            raise DCCConnectionError("Couldn't connect to socket: %s" % x)
        self.connected = 1
        self.reactor._on_connect(self.socket)
        return self

    def listen(self):
        """Wait for a connection/reconnection from a DCC peer.

        Returns the DCCConnection object.

        The local IP address and port are available as
        self.localaddress and self.localport.  After connection from a
        peer, the peer address and port are available as
        self.peeraddress and self.peerport.
        """
        self.buffer = buffer.LineBuffer()
        self.handlers = {}
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.passive = 1
        try:
            self.socket.bind((socket.gethostbyname(socket.gethostname()), 0))
            self.localaddress, self.localport = self.socket.getsockname()
            self.socket.listen(10)
        except socket.error as x:
            raise DCCConnectionError("Couldn't bind socket: %s" % x)
        return self

    def disconnect(self, message=""):
        """Hang up the connection and close the object.

        Arguments:

            message -- Quit message.
        """
        if not self.connected:
            return

        self.connected = 0
        try:
            self.socket.shutdown(socket.SHUT_WR)
            self.socket.close()
        except socket.error:
            pass
        del self.socket
        self.reactor._handle_event(
            self,
            Event("dcc_disconnect", self.peeraddress, "", [message]))
        self.reactor._remove_connection(self)

    def process_data(self):
        """[Internal]"""

        if self.passive and not self.connected:
            conn, (self.peeraddress, self.peerport) = self.socket.accept()
            self.socket.close()
            self.socket = conn
            self.connected = 1
            log.debug("DCC connection from %s:%d", self.peeraddress,
                self.peerport)
            self.reactor._handle_event(
                self,
                Event("dcc_connect", self.peeraddress, None, None))
            return

        try:
            new_data = self.socket.recv(2 ** 14)
        except socket.error:
            # The server hung up.
            self.disconnect("Connection reset by peer")
            return
        if not new_data:
            # Read nothing: connection must be down.
            self.disconnect("Connection reset by peer")
            return

        if self.dcctype == "chat":
            self.buffer.feed(new_data)

            chunks = list(self.buffer)

            if len(self.buffer) > 2 ** 14:
                # Bad peer! Naughty peer!
                log.info("Received >16k from a peer without a newline; "
                    "disconnecting.")
                self.disconnect()
                return
        else:
            chunks = [new_data]

        command = "dccmsg"
        prefix = self.peeraddress
        target = None
        for chunk in chunks:
            log.debug("FROM PEER: %s", chunk)
            arguments = [chunk]
            log.debug("command: %s, source: %s, target: %s, arguments: %s",
                command, prefix, target, arguments)
            event = Event(command, prefix, target, arguments)
            self.reactor._handle_event(self, event)

    def privmsg(self, text):
        """
        Send text to DCC peer.

        The text will be padded with a newline if it's a DCC CHAT session.
        """
        if self.dcctype == 'chat':
            text += '\n'
        bytes = text.encode('utf-8')
        return self.send_bytes(bytes)

    def send_bytes(self, bytes):
        """
        Send data to DCC peer.
        """
        try:
            self.socket.send(bytes)
            log.debug("TO PEER: %r\n", bytes)
        except socket.error:
            self.disconnect("Connection reset by peer.")


'''
PREVIOUSLY SIMPLE CLIENT:

    def _dispatcher(self, connection, event):
        """
        Dispatch events to on_<event.type> method, if present.
        """
        log.debug("_dispatcher: %s", event.type)

        do_nothing = lambda c, e: None
        method = getattr(self, "on_" + event.type, do_nothing)
        method(connection, event)

    def _dcc_disconnect(self, c, e):
        self.dcc_connections.remove(c)

    def connect(self, *args, **kwargs):
        """Connect using the underlying connection"""
        self.connection.connect(*args, **kwargs)

    def dcc_connect(self, address, port, dcctype="chat"):
        """Connect to a DCC peer.

        Arguments:

            address -- IP address of the peer.

            port -- Port to connect to.

        Returns a DCCConnection instance.
        """
        dcc = self.reactor.dcc(dcctype)
        self.dcc_connections.append(dcc)
        dcc.connect(address, port)
        return dcc

    def dcc_listen(self, dcctype="chat"):
        """Listen for connections from a DCC peer.

        Returns a DCCConnection instance.
        """
        dcc = self.reactor.dcc(dcctype)
        self.dcc_connections.append(dcc)
        dcc.listen()
        return dcc

    def start(self):
        """Start the IRC client."""
        self.reactor.process_forever()
'''

class Event(object):
    """
    An IRC event.

    >>> print(Event('privmsg', '@somebody', '#channel'))
    type: privmsg, source: @somebody, target: #channel, arguments: [], tags: []
    """
    def __init__(self, type, source, target, arguments=None, tags=None):
        """
        Initialize an Event.

        Arguments:

            type -- A string describing the event.

            source -- The originator of the event (a nick mask or a server).

            target -- The target of the event (a nick or a channel).

            arguments -- Any event-specific arguments.
        """
        self.type = type
        self.source = source
        self.target = target
        if arguments is None:
            arguments = []
        self.arguments = arguments
        if tags is None:
            tags = []
        self.tags = tags

    def __str__(self):
        tmpl = (
            "type: {type}, "
            "source: {source}, "
            "target: {target}, "
            "arguments: {arguments}, "
            "tags: {tags}"
        )
        return tmpl.format(**vars(self))


def is_channel(string):
    """Check if a string is a channel name.

    Returns true if the argument is a channel name, otherwise false.
    """
    return string and string[0] in "#&+!"

def ip_numstr_to_quad(num):
    """
    Convert an IP number as an integer given in ASCII
    representation to an IP address string.

    >>> ip_numstr_to_quad('3232235521')
    '192.168.0.1'
    >>> ip_numstr_to_quad(3232235521)
    '192.168.0.1'
    """
    n = int(num)
    packed = struct.pack('>L', n)
    bytes = struct.unpack('BBBB', packed)
    return ".".join(map(str, bytes))

def ip_quad_to_numstr(quad):
    """
    Convert an IP address string (e.g. '192.168.0.1') to an IP
    number as a base-10 integer given in ASCII representation.

    >>> ip_quad_to_numstr('192.168.0.1')
    '3232235521'
    """
    bytes = map(int, quad.split("."))
    packed = struct.pack('BBBB', *bytes)
    return str(struct.unpack('>L', packed)[0])

class NickMask(six.text_type):
    """
    A nickmask (the source of an Event)

    >>> nm = NickMask('pinky!username@example.com')
    >>> nm.nick
    'pinky'

    >>> nm.host
    'example.com'

    >>> nm.user
    'username'

    >>> isinstance(nm, six.text_type)
    True

    >>> nm = 'красный!red@yahoo.ru'
    >>> if not six.PY3: nm = nm.decode('utf-8')
    >>> nm = NickMask(nm)

    >>> isinstance(nm.nick, six.text_type)
    True

    Some messages omit the userhost. In that case, None is returned.

    >>> nm = NickMask('irc.server.net')
    >>> nm.nick
    'irc.server.net'
    >>> nm.userhost
    >>> nm.host
    >>> nm.user
    """
    @classmethod
    def from_params(cls, nick, user, host):
        return cls('{nick}!{user}@{host}'.format(**vars()))

    @property
    def nick(self):
        nick, sep, userhost = self.partition("!")
        return nick

    @property
    def userhost(self):
        nick, sep, userhost = self.partition("!")
        return userhost or None

    @property
    def host(self):
        nick, sep, userhost = self.partition("!")
        user, sep, host = userhost.partition('@')
        return host or None

    @property
    def user(self):
        nick, sep, userhost = self.partition("!")
        user, sep, host = userhost.partition('@')
        return user or None

    @classmethod
    def from_group(cls, group):
        return cls(group) if group else None


def _ping_ponger(connection, event):
    "A global handler for the 'ping' event"
    connection.pong(event.target)
