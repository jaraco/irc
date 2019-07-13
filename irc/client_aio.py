# -*- coding: utf-8 -*-

"""
Internet Relay Chat (IRC) asyncio-based protocol client library.

This an extension of the IRC client framework in irc.client that replaces
original select-based event loop with one that uses Python 3's native
asyncio event loop.

This implementation shares many of the features of its select-based
cousin, including:

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
  * DCC chat has not yet been implemented
  * DCC file transfers are not suppored
  * RFCs 2810, 2811, 2812, and 2813 have not been considered.

Notes:
  * connection.quit() only sends QUIT to the server.
  * ERROR from the server triggers the error event and the disconnect event.
  * dropping of the connection triggers the disconnect event.
"""

import asyncio
import threading
import logging

from . import connection
from .client import (
    ServerConnection,
    ServerNotConnectedError,
    Reactor,
    SimpleIRCClient,
    Event,
    _ping_ponger,
)

log = logging.getLogger(__name__)


class IrcProtocol(asyncio.Protocol):
    """
    simple asyncio-based Protocol for handling connections to
    the IRC Server.

    Note: In order to maintain a consistent interface with
    `irc.ServerConnection`, handling of incoming and outgoing data
    is mostly handling by the `AioConnection` object, using the same
    callback methods as on an `irc.ServerConnection` instance.
    """

    def __init__(self, connection, loop):
        """
        Constructor for IrcProtocol objects.
        """
        self.connection = connection
        self.loop = loop

    def data_received(self, data):
        self.connection.process_data(data)

    def connection_lost(self, exc):
        log.debug("connection lost: {}".format(exc))
        self.connection.disconnect()


class AioConnection(ServerConnection):
    """
    An IRC server connection.

    AioConnection objects are instantiated by calling the server
    method on a AioReactor object.

    Note: because AioConnection inherits from
    irc.client.ServerConnection, it has all the convenience
    methods on ServerConnection for handling outgoing data,
    including (but not limited to):

        * join(channel, key="")
        * part(channel, message="")
        * privmsg(target, text)
        * privmsg_many(targets, text)
        * quit(message="")

    And many more.  See the documentation on
    irc.client.ServerConnection for a full list of convience
    functions available.
    """

    protocol_class = IrcProtocol

    async def connect(
        self,
        server,
        port,
        nickname,
        password=None,
        username=None,
        ircname=None,
        connect_factory=connection.AioFactory(),
    ):
        """Connect/reconnect to a server.

        Arguments:

        * server - Server name
        * port - Port number
        * nickname - The nickname
        * password - Password (if any)
        * username - The username
        * ircname - The IRC name ("realname")

        * connect_factory - An async callable that takes the event loop and the
          server address, and returns a connection (with a socket interface)

        This function can be called to reconnect a closed connection.

        Returns the AioProtocol instance (used for handling incoming
        IRC data) and the transport instance (used for handling
        outgoing data).
        """
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

        protocol_instance = self.protocol_class(self, self.reactor.loop)
        connection = self.connect_factory(protocol_instance, self.server_address)
        transport, protocol = await connection

        self.transport = transport
        self.protocol = protocol

        self.connected = True
        self.reactor._on_connect(self.protocol, self.transport)

        # Log on...
        if self.password:
            self.pass_(self.password)
        self.nick(self.nickname)
        self.user(self.username, self.ircname)
        return self

    def process_data(self, new_data):
        """
        handles incoming data from the `IrcProtocol` connection.
        Main data processing/routing is handled by the _process_line
        method, inherited from `ServerConnection`
        """
        self.buffer.feed(new_data)

        # process each non-empty line after logging all lines
        for line in self.buffer:
            log.debug("FROM SERVER: %s", line)
            if not line:
                continue
            self._process_line(line)

    def send_raw(self, string):
        """Send raw string to the server, via the asyncio transport.

        The string will be padded with appropriate CR LF.
        """
        log.debug('RAW: {}'.format(string))
        if self.transport is None:
            raise ServerNotConnectedError("Not connected.")

        self.transport.write(self._prep_message(string))

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

        self.transport.close()

        self._handle_event(Event("disconnect", self.server, "", [message]))


class AioReactor(Reactor):
    """
    Processes message from on or more asyncio-based IRC server connections.

    This class inherits most of its functionality from irc.client.Reactor,
    and mainly replaces the select-based loop from that reactor with
    an asyncio event loop.

    Note: if not event loop is passed into AioReactor, it will try to get
    the current loop.  However, if there is a specific event loop
    you'd like to use, you can pass that loop by using the `loop` kwarg
    in the AioReactor's constructor:

        async def my_repeating_message(connection):
            while True:
                connection.privmsg('#my-irc-channel', 'hello!')
                await asyncio.sleep(60)

        my_loop = asyncio.get_event_loop()

        client = AioReactor(loop=my_loop)
        server = client.server()

        # use `my_loop` to initialize the repeating message on the same
        # loop as the AioRector
        asyncio.ensure_future(my_repeating_message(server), loop=my_loop)

        # connect to the server, start the loop
        server.connect('my.irc.server', 6667, 'my_irc_nick')
        client.process_forever()

    The above code will connect to the IRC server my.irc.server
    and echo the 'hello!' message to 'my-irc-channel' every 60 seconds.
    """

    connection_class = AioConnection

    def __do_nothing(*args, **kwargs):
        pass

    def __init__(self, on_connect=__do_nothing, on_disconnect=__do_nothing, loop=None):
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect

        self.connections = []
        self.handlers = {}

        self.mutex = threading.RLock()

        self.loop = asyncio.get_event_loop() if loop is None else loop

        self.add_global_handler("ping", _ping_ponger, -42)

    def process_forever(self):
        """Run an infinite loop, processing data from connections.

        Rather than call `process_once` repeatedly, like
        irc.client.reactor, incoming data is handled via the
        asycio.Protocol class -- by default, the IrcProtocol
        class definied above.
        """
        self.loop.run_forever()


class AioSimpleIRCClient(SimpleIRCClient):
    """A simple single-server IRC client class.

    This class is functionally equivalent irc.client.SimpleIRCClient,
    the only difference being the using of the AioReactor for
    asyncio-based loops.

    For more information on AioSimpleIRCClient, see the documentation
    on irc.client.SimpleIRCClient
    """

    reactor_class = AioReactor

    def connect(self, *args, **kwargs):
        self.reactor.loop.run_until_complete(self.connection.connect(*args, **kwargs))
