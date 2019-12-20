# -*- coding: utf-8 -*-

"""
Internet Relay Chat (IRC) protocol client library.

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
    specification subtleties.
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
import warnings

try:
    from importlib import metadata
except ImportError:
    import importlib_metadata as metadata

import jaraco.functools
from jaraco.functools import Throttler
from jaraco.stream import buffer
from more_itertools import consume, always_iterable, repeatfunc

from . import connection
from . import events
from . import features
from . import ctcp
from . import message
from . import schedule

log = logging.getLogger(__name__)

# set the version tuple
try:
    VERSION_STRING = metadata.version('irc')
    VERSION = tuple(int(res) for res in re.findall(r'\d+', VERSION_STRING))
except Exception:
    VERSION_STRING = 'unknown'
    VERSION = ()


class IRCError(Exception):
    "An IRC exception"


class InvalidCharacters(ValueError):
    "Invalid characters were encountered in the message"


class MessageTooLong(ValueError):
    "Message is too long"


class Connection(metaclass=abc.ABCMeta):
    """
    Base class for IRC connections.
    """

    transmit_encoding = 'utf-8'
    "encoding used for transmission"

    @abc.abstractproperty
    def socket(self):
        "The socket for this connection"

    def __init__(self, reactor):
        self.reactor = reactor

    def encode(self, msg):
        """Encode a message for transmission."""
        return msg.encode(self.transmit_encoding)


class ServerConnectionError(IRCError):
    pass


class ServerNotConnectedError(ServerConnectionError):
    pass


class ServerConnection(Connection):
    """
    An IRC server connection.

    ServerConnection objects are instantiated by calling the server
    method on a Reactor object.
    """

    buffer_class = buffer.DecodingLineBuffer
    socket = None
    connected = False

    def __init__(self, reactor):
        super(ServerConnection, self).__init__(reactor)
        self.features = features.FeatureSet()

    # save the method args to allow for easier reconnection.
    @jaraco.functools.save_method_args
    def connect(
        self,
        server,
        port,
        nickname,
        password=None,
        username=None,
        ircname=None,
        connect_factory=connection.Factory(),
    ):
        """Connect/reconnect to a server.

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

        This function can be called to reconnect a closed connection.

        Returns the ServerConnection object.
        """
        log.debug(
            "connect(server=%r, port=%r, nickname=%r, ...)", server, port, nickname
        )

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
        except socket.error as ex:
            raise ServerConnectionError("Couldn't connect to socket: %s" % ex)
        self.connected = True
        self.reactor._on_connect(self.socket)

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
        with self.reactor.mutex:
            self.disconnect("Closing object")
            self.reactor._remove_connection(self)

    def get_server_name(self):
        """Get the (real) server name.

        This method returns the (real) server name, or, more
        specifically, what the server calls itself.
        """
        return self.real_server_name or ""

    def get_nickname(self):
        """Get the (real) nick name.

        This method returns the (real) nickname.  The library keeps
        track of nick changes, so it might not be the nick name that
        was passed to the connect() method.
        """
        return self.real_nickname

    @contextlib.contextmanager
    def as_nick(self, name):
        """
        Set the nick for the duration of the context.
        """
        orig = self.get_nickname()
        self.nick(name)
        try:
            yield orig
        finally:
            self.nick(orig)

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
            if not line:
                continue
            self._process_line(line)

    def _process_line(self, line):
        event = Event("all_raw_messages", self.get_server_name(), None, [line])
        self._handle_event(event)

        grp = _rfc_1459_command_regexp.match(line).group

        source = NickMask.from_group(grp("prefix"))
        command = self._command_from_group(grp("command"))
        arguments = message.Arguments.from_group(grp('argument'))
        tags = message.Tag.from_group(grp('tags'))

        if source and not self.real_server_name:
            self.real_server_name = source

        if command == "nick":
            if source.nick == self.real_nickname:
                self.real_nickname = arguments[0]
        elif command == "welcome":
            # Record the nickname in case the client changed nick
            # in a nicknameinuse callback.
            self.real_nickname = arguments[0]
        elif command == "featurelist":
            self.features.load(arguments)

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
                log.debug(
                    "command: %s, source: %s, target: %s, " "arguments: %s, tags: %s",
                    command,
                    source,
                    target,
                    m,
                    tags,
                )
                event = Event(command, source, target, m, tags)
                self._handle_event(event)
                if command == "ctcp" and m[0] == "ACTION":
                    event = Event("action", source, target, m[1:], tags)
                    self._handle_event(event)
            else:
                log.debug(
                    "command: %s, source: %s, target: %s, " "arguments: %s, tags: %s",
                    command,
                    source,
                    target,
                    [m],
                    tags,
                )
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
        log.debug(
            "command: %s, source: %s, target: %s, " "arguments: %s, tags: %s",
            command,
            source,
            target,
            arguments,
            tags,
        )
        event = Event(command, source, target, arguments, tags)
        self._handle_event(event)

    @staticmethod
    def _command_from_group(group):
        command = group.lower()
        # Translate numerics into more readable strings.
        return events.numeric.get(command, command)

    def _handle_event(self, event):
        """[Internal]"""
        self.reactor._handle_event(self, event)
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
        self.reactor.add_global_handler(*args)

    def remove_global_handler(self, *args):
        """Remove global handler.

        See documentation for IRC.remove_global_handler.
        """
        self.reactor.remove_global_handler(*args)

    def action(self, target, action):
        """Send a CTCP ACTION command."""
        self.ctcp("ACTION", target, action)

    def admin(self, server=""):
        """Send an ADMIN command."""
        self.send_items('ADMIN', server)

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
        client_subcommands = set(cap_subcommands) - {'NAK'}
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

        self.send_items('CAP', subcommand, *_multi_parameter(args))

    def ctcp(self, ctcptype, target, parameter=""):
        """Send a CTCP command."""
        ctcptype = ctcptype.upper()
        tmpl = "\001{ctcptype} {parameter}\001" if parameter else "\001{ctcptype}\001"
        self.privmsg(target, tmpl.format(**vars()))

    def ctcp_reply(self, target, parameter):
        """Send a CTCP REPLY command."""
        self.notice(target, "\001%s\001" % parameter)

    def disconnect(self, message=""):
        """Hang up the connection.

        Arguments:

            message -- Quit message.
        """
        try:
            del self.connected
        except AttributeError:
            return

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
        self.send_items('GLOBOPS', ':' + text)

    def info(self, server=""):
        """Send an INFO command."""
        self.send_items('INFO', server)

    def invite(self, nick, channel):
        """Send an INVITE command."""
        self.send_items('INVITE', nick, channel)

    def ison(self, nicks):
        """Send an ISON command.

        Arguments:

            nicks -- List of nicks.
        """
        self.send_items('ISON', *tuple(nicks))

    def join(self, channel, key=""):
        """Send a JOIN command."""
        self.send_items('JOIN', channel, key)

    def kick(self, channel, nick, comment=""):
        """Send a KICK command."""
        self.send_items('KICK', channel, nick, comment and ':' + comment)

    def links(self, remote_server="", server_mask=""):
        """Send a LINKS command."""
        self.send_items('LINKS', remote_server, server_mask)

    def list(self, channels=None, server=""):
        """Send a LIST command."""
        self.send_items('LIST', ','.join(always_iterable(channels)), server)

    def lusers(self, server=""):
        """Send a LUSERS command."""
        self.send_items('LUSERS', server)

    def mode(self, target, command):
        """Send a MODE command."""
        self.send_items('MODE', target, command)

    def motd(self, server=""):
        """Send an MOTD command."""
        self.send_items('MOTD', server)

    def names(self, channels=None):
        """Send a NAMES command."""
        self.send_items('NAMES', ','.join(always_iterable(channels)))

    def nick(self, newnick):
        """Send a NICK command."""
        self.send_items('NICK', newnick)

    def notice(self, target, text):
        """Send a NOTICE command."""
        # Should limit len(text) here!
        self.send_items('NOTICE', target, ':' + text)

    def oper(self, nick, password):
        """Send an OPER command."""
        self.send_items('OPER', nick, password)

    def part(self, channels, message=""):
        """Send a PART command."""
        self.send_items('PART', ','.join(always_iterable(channels)), message)

    def pass_(self, password):
        """Send a PASS command."""
        self.send_items('PASS', password)

    def ping(self, target, target2=""):
        """Send a PING command."""
        self.send_items('PING', target, target2)

    def pong(self, target, target2=""):
        """Send a PONG command."""
        self.send_items('PONG', target, target2)

    def privmsg(self, target, text):
        """Send a PRIVMSG command."""
        self.send_items('PRIVMSG', target, ':' + text)

    def privmsg_many(self, targets, text):
        """Send a PRIVMSG command to multiple targets."""
        target = ','.join(targets)
        return self.privmsg(target, text)

    def quit(self, message=""):
        """Send a QUIT command."""
        # Note that many IRC servers don't use your QUIT message
        # unless you've been connected for at least 5 minutes!
        self.send_items('QUIT', message and ':' + message)

    def _prep_message(self, string):
        # The string should not contain any carriage return other than the
        # one added here.
        if '\n' in string:
            msg = "Carriage returns not allowed in privmsg(text)"
            raise InvalidCharacters(msg)
        bytes = self.encode(string) + b'\r\n'
        # According to the RFC http://tools.ietf.org/html/rfc2812#page-6,
        # clients should not transmit more than 512 bytes.
        if len(bytes) > 512:
            msg = "Messages limited to 512 bytes including CR/LF"
            raise MessageTooLong(msg)
        return bytes

    def send_items(self, *items):
        """
        Send all non-empty items, separated by spaces.
        """
        self.send_raw(' '.join(filter(None, items)))

    def send_raw(self, string):
        """Send raw string to the server.

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
        self.send_items('SQUIT', server, comment and ':' + comment)

    def stats(self, statstype, server=""):
        """Send a STATS command."""
        self.send_items('STATS', statstype, server)

    def time(self, server=""):
        """Send a TIME command."""
        self.send_items('TIME', server)

    def topic(self, channel, new_topic=None):
        """Send a TOPIC command."""
        self.send_items('TOPIC', channel, new_topic and ':' + new_topic)

    def trace(self, target=""):
        """Send a TRACE command."""
        self.send_items('TRACE', target)

    def user(self, username, realname):
        """Send a USER command."""
        cmd = 'USER {username} 0 * :{realname}'.format(**locals())
        self.send_raw(cmd)

    def userhost(self, nicks):
        """Send a USERHOST command."""
        self.send_items('USERHOST', ",".join(nicks))

    def users(self, server=""):
        """Send a USERS command."""
        self.send_items('USERS', server)

    def version(self, server=""):
        """Send a VERSION command."""
        self.send_items('VERSION', server)

    def wallops(self, text):
        """Send a WALLOPS command."""
        self.send_items('WALLOPS', ':' + text)

    def who(self, target="", op=""):
        """Send a WHO command."""
        self.send_items('WHO', target, op and 'o')

    def whois(self, targets):
        """Send a WHOIS command."""
        self.send_items('WHOIS', ",".join(always_iterable(targets)))

    def whowas(self, nick, max="", server=""):
        """Send a WHOWAS command."""
        self.send_items('WHOWAS', nick, max, server)

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
        self.reactor.scheduler.execute_every(period=interval, func=pinger)


class PrioritizedHandler(collections.namedtuple('Base', ('priority', 'callback'))):
    def __lt__(self, other):
        "when sorting prioritized handlers, only use the priority"
        return self.priority < other.priority


class Reactor:
    """
    Processes events from one or more IRC server connections.

    This class implements a reactor in the style of the `reactor pattern
    <http://en.wikipedia.org/wiki/Reactor_pattern>`_.

    When a Reactor object has been instantiated, it can be used to create
    Connection objects that represent the IRC connections.  The
    responsibility of the reactor object is to provide an event-driven
    framework for the connections and to keep the connections alive.
    It runs a select loop to poll each connection's TCP socket and
    hands over the sockets with incoming data for processing by the
    corresponding connection.

    The methods of most interest for an IRC client writer are server,
    add_global_handler, remove_global_handler,
    process_once, and process_forever.

    This is functionally an event-loop which can either use it's own
    internal polling loop, or tie into an external event-loop, by
    having the external event-system periodically call `process_once`
    on the instantiated reactor class. This will allow the reactor
    to process any queued data and/or events.

    Calling `process_forever` will hand off execution to the reactor's
    internal event-loop, which will not return for the life of the
    reactor.

    Here is an example:

        client = irc.client.Reactor()
        server = client.server()
        server.connect("irc.some.where", 6667, "my_nickname")
        server.privmsg("a_nickname", "Hi there!")
        client.process_forever()

    This will connect to the IRC server irc.some.where on port 6667
    using the nickname my_nickname and send the message "Hi there!"
    to the nickname a_nickname.

    The methods of this class are thread-safe; accesses to and modifications
    of its internal lists of connections, handlers, and delayed commands
    are guarded by a mutex.
    """

    scheduler_class = schedule.DefaultScheduler
    connection_class = ServerConnection

    def __do_nothing(*args, **kwargs):
        pass

    def __init__(self, on_connect=__do_nothing, on_disconnect=__do_nothing):
        """Constructor for Reactor objects.

        on_connect: optional callback invoked when a new connection
        is made.

        on_disconnect: optional callback invoked when a socket is
        disconnected.

        The arguments mainly exist to be able to use an external
        main loop (for example Tkinter's or PyGTK's main app loop)
        instead of calling the process_forever method.

        An alternative is to just call ServerConnection.process_once()
        once in a while.
        """

        self._on_connect = on_connect
        self._on_disconnect = on_disconnect

        scheduler = self.scheduler_class()
        assert isinstance(scheduler, schedule.IScheduler)
        self.scheduler = scheduler

        self.connections = []
        self.handlers = {}
        # Modifications to these shared lists and dict need to be thread-safe
        self.mutex = threading.RLock()

        self.add_global_handler("ping", _ping_ponger, -42)

    def server(self):
        """Creates and returns a ServerConnection object."""

        conn = self.connection_class(self)
        with self.mutex:
            self.connections.append(conn)
        return conn

    def process_data(self, sockets):
        """Called when there is more data to read on connection sockets.

        Arguments:

            sockets -- A list of socket objects.

        See documentation for Reactor.__init__.
        """
        with self.mutex:
            log.log(logging.DEBUG - 2, "process_data()")
            for sock, conn in itertools.product(sockets, self.connections):
                if sock == conn.socket:
                    conn.process_data()

    def process_timeout(self):
        """Called when a timeout notification is due.

        See documentation for Reactor.__init__.
        """
        with self.mutex:
            self.scheduler.run_pending()

    @property
    def sockets(self):
        with self.mutex:
            return [
                conn.socket
                for conn in self.connections
                if conn is not None and conn.socket is not None
            ]

    def process_once(self, timeout=0):
        """Process data from connections once.

        Arguments:

            timeout -- How long the select() call should wait if no
                       data is available.

        This method should be called periodically to check and process
        incoming data, if there are any.  If that seems boring, look
        at the process_forever method.
        """
        log.log(logging.DEBUG - 2, "process_once()")
        sockets = self.sockets
        if sockets:
            in_, out, err = select.select(sockets, [], [], timeout)
            self.process_data(in_)
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
        # the shared state of a Reactor object running this function.
        log.debug("process_forever(timeout=%s)", timeout)
        one = functools.partial(self.process_once, timeout=timeout)
        consume(repeatfunc(one))

    def disconnect_all(self, message=""):
        """Disconnects all connections."""
        with self.mutex:
            for conn in self.connections:
                conn.disconnect(message)

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
            if event not in self.handlers:
                return 0
            for h in self.handlers[event]:
                if handler == h.callback:
                    self.handlers[event].remove(h)
        return 1

    def dcc(self, dcctype="chat"):
        """Creates and returns a DCCConnection object.

        Arguments:

            dcctype -- "chat" for DCC CHAT connections or "raw" for
                       DCC SEND (or other DCC types). If "chat",
                       incoming data will be split in newline-separated
                       chunks. If "raw", incoming data is not touched.
        """
        with self.mutex:
            conn = DCCConnection(self, dcctype)
            self.connections.append(conn)
        return conn

    def _handle_event(self, connection, event):
        """
        Handle an Event event incoming on ServerConnection connection.
        """
        with self.mutex:
            matching_handlers = sorted(
                self.handlers.get("all_events", []) + self.handlers.get(event.type, [])
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


_cmd_pat = (
    "^(@(?P<tags>[^ ]*) )?(:(?P<prefix>[^ ]+) +)?"
    "(?P<command>[^ ]+)( *(?P<argument> .+))?"
)
_rfc_1459_command_regexp = re.compile(_cmd_pat)


class DCCConnectionError(IRCError):
    pass


class DCCConnection(Connection):
    """
    A DCC (Direct Client Connection).

    DCCConnection objects are instantiated by calling the dcc
    method on a Reactor object.
    """

    socket = None
    connected = False
    passive = False
    peeraddress = None
    peerport = None

    def __init__(self, reactor, dcctype):
        super(DCCConnection, self).__init__(reactor)
        self.dcctype = dcctype

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
        try:
            self.socket.connect((self.peeraddress, self.peerport))
        except socket.error as x:
            raise DCCConnectionError("Couldn't connect to socket: %s" % x)
        self.connected = True
        self.reactor._on_connect(self.socket)
        return self

    def listen(self, addr=None):
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
        self.passive = True
        default_addr = socket.gethostbyname(socket.gethostname()), 0
        try:
            self.socket.bind(addr or default_addr)
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
        try:
            del self.connected
        except AttributeError:
            return

        try:
            self.socket.shutdown(socket.SHUT_WR)
            self.socket.close()
        except socket.error:
            pass
        del self.socket
        self.reactor._handle_event(
            self, Event("dcc_disconnect", self.peeraddress, "", [message])
        )
        self.reactor._remove_connection(self)

    def process_data(self):
        """[Internal]"""

        if self.passive and not self.connected:
            conn, (self.peeraddress, self.peerport) = self.socket.accept()
            self.socket.close()
            self.socket = conn
            self.connected = True
            log.debug("DCC connection from %s:%d", self.peeraddress, self.peerport)
            self.reactor._handle_event(
                self, Event("dcc_connect", self.peeraddress, None, None)
            )
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
                log.info(
                    "Received >16k from a peer without a newline; " "disconnecting."
                )
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
            log.debug(
                "command: %s, source: %s, target: %s, arguments: %s",
                command,
                prefix,
                target,
                arguments,
            )
            event = Event(command, prefix, target, arguments)
            self.reactor._handle_event(self, event)

    def privmsg(self, text):
        """
        Send text to DCC peer.

        The text will be padded with a newline if it's a DCC CHAT session.
        """
        if self.dcctype == 'chat':
            text += '\n'
        return self.send_bytes(self.encode(text))

    def send_bytes(self, bytes):
        """
        Send data to DCC peer.
        """
        try:
            self.socket.send(bytes)
            log.debug("TO PEER: %r\n", bytes)
        except socket.error:
            self.disconnect("Connection reset by peer.")


class SimpleIRCClient:
    """A simple single-server IRC client class.

    This is an example of an object-oriented wrapper of the IRC
    framework.  A real IRC client can be made by subclassing this
    class and adding appropriate methods.

    The method on_join will be called when a "join" event is created
    (which is done when the server sends a JOIN messsage/command),
    on_privmsg will be called for "privmsg" events, and so on.  The
    handler methods get two arguments: the connection object (same as
    self.connection) and the event object.

    Functionally, any of the event names in `events.py` may be subscribed
    to by prefixing them with `on_`, and creating a function of that
    name in the child-class of `SimpleIRCClient`. When the event of
    `event_name` is received, the appropriately named method will be
    called (if it exists) by runtime class introspection.

    See `_dispatcher()`, which takes the event name, postpends it to
    `on_`, and then attemps to look up the class member function by
    name and call it.

    Instance attributes that can be used by sub classes:

        reactor -- The Reactor instance.

        connection -- The ServerConnection instance.

        dcc_connections -- A list of DCCConnection instances.
    """

    reactor_class = Reactor

    def __init__(self):
        self.reactor = self.reactor_class()
        self.connection = self.reactor.server()
        self.dcc_connections = []
        self.reactor.add_global_handler("all_events", self._dispatcher, -10)
        self.reactor.add_global_handler("dcc_disconnect", self._dcc_disconnect, -10)

    def _dispatcher(self, connection, event):
        """
        Dispatch events to on_<event.type> method, if present.
        """
        log.debug("_dispatcher: %s", event.type)

        def do_nothing(connection, event):
            return None

        method = getattr(self, "on_" + event.type, do_nothing)
        method(connection, event)

    def _dcc_disconnect(self, connection, event):
        self.dcc_connections.remove(connection)

    def connect(self, *args, **kwargs):
        """Connect using the underlying connection"""
        self.connection.connect(*args, **kwargs)

    def dcc(self, *args, **kwargs):
        """Create and associate a new DCCConnection object.

        Use the returned object to listen for or connect to
        a DCC peer.
        """
        dcc = self.reactor.dcc(*args, **kwargs)
        self.dcc_connections.append(dcc)
        return dcc

    def dcc_connect(self, address, port, dcctype="chat"):
        """Connect to a DCC peer.

        Arguments:

            address -- IP address of the peer.

            port -- Port to connect to.

        Returns a DCCConnection instance.
        """
        warnings.warn("Use self.dcc(type).connect()", DeprecationWarning)
        return self.dcc(dcctype).connect(address, port)

    def dcc_listen(self, dcctype="chat"):
        """Listen for connections from a DCC peer.

        Returns a DCCConnection instance.
        """
        warnings.warn("Use self.dcc(type).listen()", DeprecationWarning)
        return self.dcc(dcctype).listen()

    def start(self):
        """Start the IRC client."""
        self.reactor.process_forever()


class Event:
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
    packed = struct.pack('>L', int(num))
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


class NickMask(str):
    """
    A nickmask (the source of an Event)

    >>> nm = NickMask('pinky!username@example.com')
    >>> nm.nick
    'pinky'

    >>> nm.host
    'example.com'

    >>> nm.user
    'username'

    >>> isinstance(nm, str)
    True

    >>> nm = NickMask('красный!red@yahoo.ru')

    >>> isinstance(nm.nick, str)
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
