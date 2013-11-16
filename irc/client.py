# -*- coding: utf-8 -*-

# Copyright (C) 1999-2002  Joel Rosdahl
# Copyright © 2011-2013 Jason R. Coombs

"""
Internet Relay Chat (IRC) protocol client library.

This library is intended to encapsulate the IRC protocol at a quite
low level.  It provides an event-driven IRC client framework.  It has
a fairly thorough support for the basic IRC protocol, CTCP, DCC chat,
but DCC file transfers is not yet supported.

In order to understand how to make an IRC client, I'm afraid you more
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

  * The IRC protocol shines through the abstraction a bit too much.
  * Data is not written asynchronously to the server, i.e. the write()
    may block if the TCP buffers are stuffed.
  * There are no support for DCC file transfers.
  * The author haven't even read RFC 2810, 2811, 2812 and 2813.
  * Like most projects, documentation is lacking...

.. [IRC specifications] http://www.irchelp.org/irchelp/rfc/
"""

from __future__ import absolute_import, division

import bisect
import re
import select
import socket
import string
import time
import struct
import logging
import threading
import abc
import collections
import functools
import itertools

import six

try:
    import pkg_resources
except ImportError:
    pass

from . import connection
from . import events
from . import functools as irc_functools
from . import strings
from . import util
from . import buffer
from . import schedule
from . import features

log = logging.getLogger(__name__)

# set the version tuple
try:
    VERSION_STRING = pkg_resources.require('irc')[0].version
    VERSION = tuple(int(res) for res in re.findall('\d+', VERSION_STRING))
except Exception:
    VERSION_STRING = 'unknown'
    VERSION = ()

# TODO
# ----
# (maybe) color parser convenience functions
# documentation (including all event types)
# (maybe) add awareness of different types of ircds
# send data asynchronously to the server (and DCC connections)
# (maybe) automatically close unused, passive DCC connections after a while

# NOTES
# -----
# connection.quit() only sends QUIT to the server.
# ERROR from the server triggers the error event and the disconnect event.
# dropping of the connection triggers the disconnect event.

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

class IRC(object):
    """Class that handles one or several IRC server connections.

    When an IRC object has been instantiated, it can be used to create
    Connection objects that represent the IRC connections.  The
    responsibility of the IRC object is to provide an event-driven
    framework for the connections and to keep the connections alive.
    It runs a select loop to poll each connection's TCP socket and
    hands over the sockets with incoming data for processing by the
    corresponding connection.

    The methods of most interest for an IRC client writer are server,
    add_global_handler, remove_global_handler, execute_at,
    execute_delayed, execute_every, process_once, and process_forever.

    Here is an example:

        client = irc.client.IRC()
        server = client.server()
        server.connect("irc.some.where", 6667, "my_nickname")
        server.privmsg("a_nickname", "Hi there!")
        client.process_forever()

    This will connect to the IRC server irc.some.where on port 6667
    using the nickname my_nickname and send the message "Hi there!"
    to the nickname a_nickname.

    The methods of this class are thread-safe; accesses to and modifications of
    its internal lists of connections, handlers, and delayed commands
    are guarded by a mutex.
    """

    def __do_nothing(*args, **kwargs):
        pass

    def __init__(self, on_connect=__do_nothing, on_disconnect=__do_nothing,
            on_schedule=__do_nothing):
        """Constructor for IRC objects.

        on_connect: optional callback invoked when a new connection
        is made.

        on_disconnect: optional callback invoked when a socket is
        disconnected.

        on_schedule: optional callback, usually supplied by an external
        event loop, to indicate in float seconds that the client needs to
        process events that many seconds in the future. An external event
        loop will implement this callback to schedule a call to
        process_timeout.

        The three arguments mainly exist to be able to use an external
        main loop (for example Tkinter's or PyGTK's main app loop)
        instead of calling the process_forever method.

        An alternative is to just call ServerConnection.process_once()
        once in a while.
        """

        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_schedule = on_schedule

        self.connections = []
        self.handlers = {}
        self.delayed_commands = []  # list of DelayedCommands
        # Modifications to these shared lists and dict need to be thread-safe
        self.mutex = threading.RLock()

        self.add_global_handler("ping", _ping_ponger, -42)

    def server(self):
        """Creates and returns a ServerConnection object."""

        c = ServerConnection(self)
        with self.mutex:
            self.connections.append(c)
        return c

    def process_data(self, sockets):
        """Called when there is more data to read on connection sockets.

        Arguments:

            sockets -- A list of socket objects.

        See documentation for IRC.__init__.
        """
        with self.mutex:
            log.log(logging.DEBUG-2, "process_data()")
            for s, c in itertools.product(sockets, self.connections):
                if s == c.socket:
                    c.process_data()

    def process_timeout(self):
        """Called when a timeout notification is due.

        See documentation for IRC.__init__.
        """
        with self.mutex:
            while self.delayed_commands:
                command = self.delayed_commands[0]
                if not command.due():
                    break
                command.function()
                if isinstance(command, schedule.PeriodicCommand):
                    self._schedule_command(command.next())
                del self.delayed_commands[0]

    def process_once(self, timeout=0):
        """Process data from connections once.

        Arguments:

            timeout -- How long the select() call should wait if no
                       data is available.

        This method should be called periodically to check and process
        incoming data, if there are any.  If that seems boring, look
        at the process_forever method.
        """
        with self.mutex:
            log.log(logging.DEBUG-2, "process_once()")
            sockets = [x.socket for x in self.connections if x is not None]
            sockets = [x for x in sockets if x is not None]
            if sockets:
                (i, o, e) = select.select(sockets, [], [], timeout)
                self.process_data(i)
            else:
                time.sleep(timeout)
            self.process_timeout()

    def process_forever(self, timeout=0.2):
        """Run an infinite loop, processing data from connections.

        This method repeatedly calls process_once.

        Arguments:

            timeout -- Parameter to pass to process_once.
        """
        # This loop should specifically *not* be mutex-locked.
        # Otherwise no other thread would ever be able to change
        # the shared state of an IRC object running this function.
        log.debug("process_forever(timeout=%s)", timeout)
        while 1:
            self.process_once(timeout)

    def disconnect_all(self, message=""):
        """Disconnects all connections."""
        with self.mutex:
            for c in self.connections:
                c.disconnect(message)

    def add_global_handler(self, event, handler, priority=0):
        """Adds a global handler function for a specific event type.

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
        "NO MORE", no more handlers will be called.
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

    def execute_at(self, at, function, arguments=()):
        """Execute a function at a specified time.

        Arguments:

            at -- Execute at this time (standard "time_t" time).
            function -- Function to call.
            arguments -- Arguments to give the function.
        """
        function = functools.partial(function, *arguments)
        command = schedule.DelayedCommand.at_time(at, function)
        self._schedule_command(command)

    def execute_delayed(self, delay, function, arguments=()):
        """
        Execute a function after a specified time.

        delay -- How many seconds to wait.
        function -- Function to call.
        arguments -- Arguments to give the function.
        """
        function = functools.partial(function, *arguments)
        command = schedule.DelayedCommand.after(delay, function)
        self._schedule_command(command)

    def execute_every(self, period, function, arguments=()):
        """
        Execute a function every 'period' seconds.

        period -- How often to run (always waits this long for first).
        function -- Function to call.
        arguments -- Arguments to give the function.
        """
        function = functools.partial(function, *arguments)
        command = schedule.PeriodicCommand.after(period, function)
        self._schedule_command(command)

    def _schedule_command(self, command):
        with self.mutex:
            bisect.insort(self.delayed_commands, command)
            self._on_schedule(util.total_seconds(command.delay))

    def dcc(self, dcctype="chat"):
        """Creates and returns a DCCConnection object.

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
        with self.mutex:
            h = self.handlers
            matching_handlers = sorted(
                h.get("all_events", []) +
                h.get(event.type, [])
            )
            for handler in matching_handlers:
                result = handler.callback(connection, event)
                if result == "NO MORE":
                    return

    def _remove_connection(self, connection):
        """[Internal]"""
        with self.mutex:
            self.connections.remove(connection)
            self._on_disconnect(connection.socket)

_rfc_1459_command_regexp = re.compile("^(:(?P<prefix>[^ ]+) +)?(?P<command>[^ ]+)( *(?P<argument> .+))?")

class Connection(object):
    """
    Base class for IRC connections.
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractproperty
    def socket(self):
        "The socket for this connection"

    def __init__(self, irclibobj):
        self.irclibobj = irclibobj

    ##############################
    ### Convenience wrappers.

    def execute_at(self, at, function, arguments=()):
        self.irclibobj.execute_at(at, function, arguments)

    def execute_delayed(self, delay, function, arguments=()):
        self.irclibobj.execute_delayed(delay, function, arguments)

    def execute_every(self, period, function, arguments=()):
        self.irclibobj.execute_every(period, function, arguments)

class ServerConnectionError(IRCError):
    pass

class ServerNotConnectedError(ServerConnectionError):
    pass


class ServerConnection(Connection):
    """
    An IRC server connection.

    ServerConnection objects are instantiated by calling the server
    method on an IRC object.
    """

    buffer_class = buffer.DecodingLineBuffer
    socket = None

    def __init__(self, irclibobj):
        super(ServerConnection, self).__init__(irclibobj)
        self.connected = False
        self.features = features.FeatureSet()

    # save the method args to allow for easier reconnection.
    @irc_functools.save_method_args
    def connect(self, server, port, nickname, password=None, username=None,
            ircname=None, connect_factory=connection.Factory()):
        """Connect/reconnect to a server.

        Arguments:

            server -- Server name.
            port -- Port number.
            nickname -- The nickname.
            password -- Password (if any).
            username -- The username.
            ircname -- The IRC name ("realname").
            server_address -- The remote host/port of the server.
            connect_factory -- A callable that takes the server address and
                returns a connection (with a socket interface).

        This function can be called to reconnect a closed connection.

        Returns the ServerConnection object.
        """
        log.debug("connect(server=%r, port=%r, nickname=%r, ...)", server,
            port, nickname)

        if self.connected:
            self.disconnect("Changing servers")

        self.buffer = self.buffer_class()
        self.handlers = {}
        self.real_server_name = ""
        self.real_nickname = nickname
        self.server = server
        self.port = port
        self.server_address = (server, port)
        self.nickname = nickname
        self.username = username or nickname
        self.ircname = ircname or nickname
        self.password = password
        self.connect_factory = connect_factory
        try:
            self.socket = self.connect_factory(self.server_address)
        except socket.error as err:
            raise ServerConnectionError("Couldn't connect to socket: %s" % err)
        self.connected = True
        self.irclibobj._on_connect(self.socket)

        # Log on...
        if self.password:
            self.pass_(self.password)
        self.nick(self.nickname)
        self.user(self.username, self.ircname)
        return self

    def reconnect(self):
        """
        Reconnect with the last arguments passed to self.connect()
        """
        self.connect(*self._saved_connect.args, **self._saved_connect.kwargs)

    def close(self):
        """Close the connection.

        This method closes the connection permanently; after it has
        been called, the object is unusable.
        """
        # Without this thread lock, there is a window during which
        # select() can find a closed socket, leading to an EBADF error.
        with self.irclibobj.mutex:
            self.disconnect("Closing object")
            self.irclibobj._remove_connection(self)

    def get_server_name(self):
        """Get the (real) server name.

        This method returns the (real) server name, or, more
        specifically, what the server calls itself.
        """

        if self.real_server_name:
            return self.real_server_name
        else:
            return ""

    def get_nickname(self):
        """Get the (real) nick name.

        This method returns the (real) nickname.  The library keeps
        track of nick changes, so it might not be the nick name that
        was passed to the connect() method.  """

        return self.real_nickname

    def process_data(self):
        "read and process input from self.socket"

        try:
            reader = getattr(self.socket, 'read', self.socket.recv)
            new_data = reader(2 ** 14)
        except socket.error:
            # The server hung up.
            self.disconnect("Connection reset by peer")
            return
        if not new_data:
            # Read nothing: connection must be down.
            self.disconnect("Connection reset by peer")
            return

        self.buffer.feed(new_data)

        # process each non-empty line after logging all lines
        for line in self.buffer:
            log.debug("FROM SERVER: %s", line)
            if not line: continue
            self._process_line(line)

    def _process_line(self, line):
        prefix = None
        command = None
        arguments = None
        self._handle_event(Event("all_raw_messages",
                                 self.get_server_name(),
                                 None,
                                 [line]))

        m = _rfc_1459_command_regexp.match(line)
        if m.group("prefix"):
            prefix = m.group("prefix")
            if not self.real_server_name:
                self.real_server_name = prefix

        if m.group("command"):
            command = m.group("command").lower()

        if m.group("argument"):
            a = m.group("argument").split(" :", 1)
            arguments = a[0].split()
            if len(a) == 2:
                arguments.append(a[1])

        # Translate numerics into more readable strings.
        command = events.numeric.get(command, command)

        if command == "nick":
            if NickMask(prefix).nick == self.real_nickname:
                self.real_nickname = arguments[0]
        elif command == "welcome":
            # Record the nickname in case the client changed nick
            # in a nicknameinuse callback.
            self.real_nickname = arguments[0]
        elif command == "featurelist":
            self.features.load(arguments)

        if command in ["privmsg", "notice"]:
            target, message = arguments[0], arguments[1]
            messages = _ctcp_dequote(message)

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
                        "arguments: %s", command, prefix, target, m)
                    self._handle_event(Event(command, NickMask(prefix), target, m))
                    if command == "ctcp" and m[0] == "ACTION":
                        self._handle_event(Event("action", prefix, target, m[1:]))
                else:
                    log.debug("command: %s, source: %s, target: %s, "
                        "arguments: %s", command, prefix, target, [m])
                    self._handle_event(Event(command, NickMask(prefix), target, [m]))
        else:
            target = None

            if command == "quit":
                arguments = [arguments[0]]
            elif command == "ping":
                target = arguments[0]
            else:
                target = arguments[0]
                arguments = arguments[1:]

            if command == "mode":
                if not is_channel(target):
                    command = "umode"

            log.debug("command: %s, source: %s, target: %s, "
                "arguments: %s", command, prefix, target, arguments)
            self._handle_event(Event(command, NickMask(prefix), target, arguments))

    def _handle_event(self, event):
        """[Internal]"""
        self.irclibobj._handle_event(self, event)
        if event.type in self.handlers:
            for fn in self.handlers[event.type]:
                fn(self, event)

    def is_connected(self):
        """Return connection status.

        Returns true if connected, otherwise false.
        """
        return self.connected

    def add_global_handler(self, *args):
        """Add global handler.

        See documentation for IRC.add_global_handler.
        """
        self.irclibobj.add_global_handler(*args)

    def remove_global_handler(self, *args):
        """Remove global handler.

        See documentation for IRC.remove_global_handler.
        """
        self.irclibobj.remove_global_handler(*args)

    def action(self, target, action):
        """Send a CTCP ACTION command."""
        self.ctcp("ACTION", target, action)

    def admin(self, server=""):
        """Send an ADMIN command."""
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

            It's not obvious where the sentinel should be present or if it must
            be omitted for a single parameter, so follow convention and only
            include the sentinel prefixed to the first parameter if more than
            one parameter is present.
            """
            if len(args) > 1:
                return (':' + args[0],) + args[1:]
            return args

        args = _multi_parameter(args)
        self.send_raw(' '.join(('CAP', subcommand) + args))

    def ctcp(self, ctcptype, target, parameter=""):
        """Send a CTCP command."""
        ctcptype = ctcptype.upper()
        self.privmsg(target, "\001%s%s\001" % (ctcptype, parameter and (" " + parameter) or ""))

    def ctcp_reply(self, target, parameter):
        """Send a CTCP REPLY command."""
        self.notice(target, "\001%s\001" % parameter)

    def disconnect(self, message=""):
        """Hang up the connection.

        Arguments:

            message -- Quit message.
        """
        if not self.connected:
            return

        self.connected = 0

        self.quit(message)

        try:
            self.socket.shutdown(socket.SHUT_WR)
            self.socket.close()
        except socket.error:
            pass
        del self.socket
        self._handle_event(Event("disconnect", self.server, "", [message]))

    def globops(self, text):
        """Send a GLOBOPS command."""
        self.send_raw("GLOBOPS :" + text)

    def info(self, server=""):
        """Send an INFO command."""
        self.send_raw(" ".join(["INFO", server]).strip())

    def invite(self, nick, channel):
        """Send an INVITE command."""
        self.send_raw(" ".join(["INVITE", nick, channel]).strip())

    def ison(self, nicks):
        """Send an ISON command.

        Arguments:

            nicks -- List of nicks.
        """
        self.send_raw("ISON " + " ".join(nicks))

    def join(self, channel, key=""):
        """Send a JOIN command."""
        self.send_raw("JOIN %s%s" % (channel, (key and (" " + key))))

    def kick(self, channel, nick, comment=""):
        """Send a KICK command."""
        self.send_raw("KICK %s %s%s" % (channel, nick, (comment and (" :" + comment))))

    def links(self, remote_server="", server_mask=""):
        """Send a LINKS command."""
        command = "LINKS"
        if remote_server:
            command = command + " " + remote_server
        if server_mask:
            command = command + " " + server_mask
        self.send_raw(command)

    def list(self, channels=None, server=""):
        """Send a LIST command."""
        command = "LIST"
        if channels:
            command = command + " " + ",".join(channels)
        if server:
            command = command + " " + server
        self.send_raw(command)

    def lusers(self, server=""):
        """Send a LUSERS command."""
        self.send_raw("LUSERS" + (server and (" " + server)))

    def mode(self, target, command):
        """Send a MODE command."""
        self.send_raw("MODE %s %s" % (target, command))

    def motd(self, server=""):
        """Send an MOTD command."""
        self.send_raw("MOTD" + (server and (" " + server)))

    def names(self, channels=None):
        """Send a NAMES command."""
        self.send_raw("NAMES" + (channels and (" " + ",".join(channels)) or ""))

    def nick(self, newnick):
        """Send a NICK command."""
        self.send_raw("NICK " + newnick)

    def notice(self, target, text):
        """Send a NOTICE command."""
        # Should limit len(text) here!
        self.send_raw("NOTICE %s :%s" % (target, text))

    def oper(self, nick, password):
        """Send an OPER command."""
        self.send_raw("OPER %s %s" % (nick, password))

    def part(self, channels, message=""):
        """Send a PART command."""
        channels = util.always_iterable(channels)
        cmd_parts = [
            'PART',
            ','.join(channels),
        ]
        if message: cmd_parts.append(message)
        self.send_raw(' '.join(cmd_parts))

    def pass_(self, password):
        """Send a PASS command."""
        self.send_raw("PASS " + password)

    def ping(self, target, target2=""):
        """Send a PING command."""
        self.send_raw("PING %s%s" % (target, target2 and (" " + target2)))

    def pong(self, target, target2=""):
        """Send a PONG command."""
        self.send_raw("PONG %s%s" % (target, target2 and (" " + target2)))

    def privmsg(self, target, text):
        """Send a PRIVMSG command."""
        self.send_raw("PRIVMSG %s :%s" % (target, text))

    def privmsg_many(self, targets, text):
        """Send a PRIVMSG command to multiple targets."""
        target = ','.join(targets)
        return self.privmsg(target, text)

    def quit(self, message=""):
        """Send a QUIT command."""
        # Note that many IRC servers don't use your QUIT message
        # unless you've been connected for at least 5 minutes!
        self.send_raw("QUIT" + (message and (" :" + message)))

    def send_raw(self, string):
        """Send raw string to the server.

        The string will be padded with appropriate CR LF.
        """
        # The string should not contain any carriage return other than the
        # one added here.
        if '\n' in string:
            raise InvalidCharacters(
                "Carriage returns not allowed in privmsg(text)")
        bytes = string.encode('utf-8') + b'\r\n'
        # According to the RFC http://tools.ietf.org/html/rfc2812#page-6,
        # clients should not transmit more than 512 bytes.
        if len(bytes) > 512:
            raise MessageTooLong(
                "Messages limited to 512 bytes including CR/LF")
        if self.socket is None:
            raise ServerNotConnectedError("Not connected.")
        sender = getattr(self.socket, 'write', self.socket.send)
        try:
            sender(bytes)
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
        self.irclibobj.execute_every(period=interval, function=pinger)


class Throttler(object):
    """
    Rate-limit a function (or other callable)
    """
    def __init__(self, func, max_rate=float('Inf')):
        if isinstance(func, Throttler):
            func = func.func
        self.func = func
        self.max_rate = max_rate
        self.reset()

    def reset(self):
        self.last_called = 0

    def __call__(self, *args, **kwargs):
        # ensure at least 1/max_rate seconds from last call
        elapsed = time.time() - self.last_called
        must_wait = 1 / self.max_rate - elapsed
        time.sleep(max(0, must_wait))
        self.last_called = time.time()
        return self.func(*args, **kwargs)


class DCCConnectionError(IRCError):
    pass


class DCCConnection(Connection):
    """
    A DCC (Direct Client Connection).

    DCCConnection objects are instantiated by calling the dcc
    method on an IRC object.
    """
    socket = None

    def __init__(self, irclibobj, dcctype):
        super(DCCConnection, self).__init__(irclibobj)
        self.connected = 0
        self.passive = 0
        self.dcctype = dcctype
        self.peeraddress = None
        self.peerport = None

    def connect(self, address, port):
        """Connect/reconnect to a DCC peer.

        Arguments:
            address -- Host/IP address of the peer.

            port -- The port number to connect to.

        Returns the DCCConnection object.
        """
        self.peeraddress = socket.gethostbyname(address)
        self.peerport = port
        self.buffer = LineBuffer()
        self.handlers = {}
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.passive = 0
        try:
            self.socket.connect((self.peeraddress, self.peerport))
        except socket.error as x:
            raise DCCConnectionError("Couldn't connect to socket: %s" % x)
        self.connected = 1
        self.irclibobj._on_connect(self.socket)
        return self

    def listen(self):
        """Wait for a connection/reconnection from a DCC peer.

        Returns the DCCConnection object.

        The local IP address and port are available as
        self.localaddress and self.localport.  After connection from a
        peer, the peer address and port are available as
        self.peeraddress and self.peerport.
        """
        self.buffer = LineBuffer()
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
        self.irclibobj._handle_event(
            self,
            Event("dcc_disconnect", self.peeraddress, "", [message]))
        self.irclibobj._remove_connection(self)

    def process_data(self):
        """[Internal]"""

        if self.passive and not self.connected:
            conn, (self.peeraddress, self.peerport) = self.socket.accept()
            self.socket.close()
            self.socket = conn
            self.connected = 1
            log.debug("DCC connection from %s:%d", self.peeraddress,
                self.peerport)
            self.irclibobj._handle_event(
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
            self.irclibobj._handle_event(
                self,
                Event(command, prefix, target, arguments))

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


class SimpleIRCClient(object):
    """A simple single-server IRC client class.

    This is an example of an object-oriented wrapper of the IRC
    framework.  A real IRC client can be made by subclassing this
    class and adding appropriate methods.

    The method on_join will be called when a "join" event is created
    (which is done when the server sends a JOIN messsage/command),
    on_privmsg will be called for "privmsg" events, and so on.  The
    handler methods get two arguments: the connection object (same as
    self.connection) and the event object.

    Instance attributes that can be used by sub classes:

        ircobj -- The IRC instance.

        connection -- The ServerConnection instance.

        dcc_connections -- A list of DCCConnection instances.
    """
    def __init__(self):
        self.ircobj = IRC()
        self.connection = self.ircobj.server()
        self.dcc_connections = []
        self.ircobj.add_global_handler("all_events", self._dispatcher, -10)
        self.ircobj.add_global_handler("dcc_disconnect", self._dcc_disconnect, -10)

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
        dcc = self.ircobj.dcc(dcctype)
        self.dcc_connections.append(dcc)
        dcc.connect(address, port)
        return dcc

    def dcc_listen(self, dcctype="chat"):
        """Listen for connections from a DCC peer.

        Returns a DCCConnection instance.
        """
        dcc = self.ircobj.dcc(dcctype)
        self.dcc_connections.append(dcc)
        dcc.listen()
        return dcc

    def start(self):
        """Start the IRC client."""
        self.ircobj.process_forever()


class Event(object):
    "An IRC event."
    def __init__(self, type, source, target, arguments=None):
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

_LOW_LEVEL_QUOTE = "\020"
_CTCP_LEVEL_QUOTE = "\134"
_CTCP_DELIMITER = "\001"

_low_level_mapping = {
    "0": "\000",
    "n": "\n",
    "r": "\r",
    _LOW_LEVEL_QUOTE: _LOW_LEVEL_QUOTE
}

_low_level_regexp = re.compile(_LOW_LEVEL_QUOTE + "(.)")

def mask_matches(nick, mask):
    """Check if a nick matches a mask.

    Returns true if the nick matches, otherwise false.
    """
    nick = strings.lower(nick)
    mask = strings.lower(mask)
    mask = mask.replace("\\", "\\\\")
    for ch in ".$|[](){}+":
        mask = mask.replace(ch, "\\" + ch)
    mask = mask.replace("?", ".")
    mask = mask.replace("*", ".*")
    r = re.compile(mask, re.IGNORECASE)
    return r.match(nick)

_special = "-[]\\`^{}"
nick_characters = string.ascii_letters + string.digits + _special

def _ctcp_dequote(message):
    """[Internal] Dequote a message according to CTCP specifications.

    The function returns a list where each element can be either a
    string (normal message) or a tuple of one or two strings (tagged
    messages).  If a tuple has only one element (ie is a singleton),
    that element is the tag; otherwise the tuple has two elements: the
    tag and the data.

    Arguments:

        message -- The message to be decoded.
    """

    def _low_level_replace(match_obj):
        ch = match_obj.group(1)

        # If low_level_mapping doesn't have the character as key, we
        # should just return the character.
        return _low_level_mapping.get(ch, ch)

    if _LOW_LEVEL_QUOTE in message:
        # Yup, there was a quote.  Release the dequoter, man!
        message = _low_level_regexp.sub(_low_level_replace, message)

    if _CTCP_DELIMITER not in message:
        return [message]
    else:
        # Split it into parts.  (Does any IRC client actually *use*
        # CTCP stacking like this?)
        chunks = message.split(_CTCP_DELIMITER)

        messages = []
        i = 0
        while i < len(chunks) - 1:
            # Add message if it's non-empty.
            if len(chunks[i]) > 0:
                messages.append(chunks[i])

            if i < len(chunks) - 2:
                # Aye!  CTCP tagged data ahead!
                messages.append(tuple(chunks[i + 1].split(" ", 1)))

            i = i + 2

        if len(chunks) % 2 == 0:
            # Hey, a lonely _CTCP_DELIMITER at the end!  This means
            # that the last chunk, including the delimiter, is a
            # normal message!  (This is according to the CTCP
            # specification.)
            messages.append(_CTCP_DELIMITER + chunks[-1])

        return messages

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
    >>> print(nm.nick)
    pinky

    >>> print(nm.host)
    example.com

    >>> print(nm.user)
    username

    >>> isinstance(nm, six.text_type)
    True

    >>> nm = 'красный!red@yahoo.ru'
    >>> if not six.PY3: nm = nm.decode('utf-8')
    >>> nm = NickMask(nm)

    >>> isinstance(nm.nick, six.text_type)
    True
    """
    @classmethod
    def from_params(cls, nick, user, host):
        return cls('{nick}!{user}@{host}'.format(**vars()))

    @property
    def nick(self):
        return self.split("!")[0]

    @property
    def userhost(self):
        return self.split("!")[1]

    @property
    def host(self):
        return self.split("@")[1]

    @property
    def user(self):
        return self.userhost.split("@")[0]

def _ping_ponger(connection, event):
    "A global handler for the 'ping' event"
    connection.pong(event.target)

# for backward compatibility
LineBuffer = buffer.LineBuffer
DecodingLineBuffer = buffer.DecodingLineBuffer
