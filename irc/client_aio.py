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
import logging
import threading

from jaraco.stream import buffer
from . import connection
from .client import (
    Event,
    Reactor,
    ServerConnection,
    ServerNotConnectedError,
    SimpleIRCClient,
    DCCConnection,
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
        log.debug(f"connection lost: {exc}")
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
        log.debug(f'RAW: {string}')
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


class DCCProtocol(IrcProtocol):
    """
    A protocol for handling DCC connections.

    Currently, DCCProtocol uses the same methods as `IrcProtocol`
    for handling incoming data.  This should be fine for most use
    cases, but in the unlikely event that a DCC connection needs to
    handle incoming data in a different way than an IRC connection,
    this class will need to be overridden.
    """


class AioDCCConnection(DCCConnection):
    """
    An asyncio-based DCCConnection.

    This class overrides select-based methods with asyncio-based ones.
    """

    rector: "AioReactor"
    buffer_class = buffer.DecodingLineBuffer

    protocol_class = DCCProtocol
    protocol: DCCProtocol
    socket: None
    connected: bool
    passive: bool
    peeraddress: str
    peerport: int

    async def connect(
        self, address: str, port: int, connect_factory: connection.AioFactory = connection.AioFactory()
    ) -> "AioDCCConnection":
        """Connect/reconnect to a DCC peer.

        Arguments:
            address -- Host/IP address of the peer.
            port -- The port number to connect to.
            connect_factory -- A callable that takes the event loop and the
              server address, and returns a connection (with a socket interface)

        Returns the DCCConnection object.
        """
        self.peeraddress = address
        self.peerport = port
        self.handlers = {}
        self.buffer = self.buffer_class()

        self.connect_factory = connect_factory
        protocol_instance = self.protocol_class(self, self.reactor.loop)
        connection = self.connect_factory(protocol_instance, (self.peeraddress, self.peerport))
        transport, protocol = await connection

        self.transport = transport
        self.protocol = protocol

        self.connected = True
        self.reactor._on_connect(self.protocol, self.transport)
        return self

    # TODO: implement listen() in asyncio way
    async def listen(self, addr=None) -> "AioDCCConnection":
        """Wait for a connection/reconnection from a DCC peer.

        Returns the DCCConnection object.

        The local IP address and port are available as
        self.peeraddress and self.peerport.
        """

        raise NotImplementedError()

    def disconnect(self, message: str = "") -> None:
        """Hang up the connection and close the object.

        Arguments:

            message -- Quit message.
        """
        try:
            del self.connected
        except AttributeError:
            return

        self.transport.close()

        self.reactor._handle_event(
            self, Event("dcc_disconnect", self.peeraddress, "", [message])
        )
        self.reactor._remove_connection(self)

    def process_data(self, new_data: bytes) -> None:
        """
        handles incoming data from the `DCCProtocol` connection.
        """

        if self.passive and not self.connected:
            raise NotImplementedError()
            # TODO: implement passive DCC connection

        if self.dcctype == "chat":
            self.buffer.feed(new_data)

            chunks = list(self.buffer)

            if len(self.buffer) > 2**14:
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

    def send_bytes(self, bytes: bytes) -> None:
        """
        Send data to DCC peer.
        """
        try:
            self.transport.write(bytes)
            log.debug("TO PEER: %r\n", bytes)
        except OSError:
            self.disconnect("Connection reset by peer.")


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
    dcc_connection_class = AioDCCConnection

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

    def dcc(self, dcctype="chat"):
        """Creates and returns a DCCConnection object.

        Arguments:

            dcctype -- "chat" for DCC CHAT connections or "raw" for
                       DCC SEND (or other DCC types). If "chat",
                       incoming data will be split in newline-separated
                       chunks. If "raw", incoming data is not touched.
        """
        with self.mutex:
            conn = self.dcc_connection_class(self, dcctype)
            self.connections.append(conn)
        return conn


class AioSimpleIRCClient(SimpleIRCClient):
    """A simple single-server IRC client class.

    This class is functionally equivalent irc.client.SimpleIRCClient,
    the only difference being the using of the AioReactor for
    asyncio-based loops.

    For more information on AioSimpleIRCClient, see the documentation
    on irc.client.SimpleIRCClient
    """

    reactor_class = AioReactor
    reactor: AioReactor

    def connect(self, *args, **kwargs):
        self.reactor.loop.run_until_complete(self.connection.connect(*args, **kwargs))
