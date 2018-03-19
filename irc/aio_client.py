import asyncio
import threading
import logging

from .client import ServerConnection, ServerConnectionError, ServerNotConnectedError, Reactor,\
     SimpleIRCClient, Event, _ping_ponger
from . import functools as irc_functools

log = logging.getLogger(__name__)


class IrcProtocol(asyncio.Protocol):
    def __init__(self, connection, loop):
        self.connection = connection
        self.loop = loop

    def data_received(self, data):
        self.connection.process_data(data)


class AioConnection(ServerConnection):
    protocol_class = IrcProtocol

    @irc_functools.save_method_args
    def connect(
            self, server, port, nickname, password=None, username=None, ircname=None
    ):
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

        connection = self.reactor.loop.create_connection(
            lambda: IrcProtocol(self, self.reactor.loop), self.server, self.port,
        )
        transport, protocol = self.reactor.loop.run_until_complete(connection)

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
        handles incoming data from the Protocol
        """
        self.buffer.feed(new_data)

        # process each non-empty line after logging all lines
        for line in self.buffer:
            log.debug("FROM SERVER: %s", line)
            if not line:
                continue
            self._process_line(line)

    def send_raw(self, string):
        """Send raw string to the server.

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
        if not self.connected:
            return

        self.connected = 0

        self.quit(message)

        self.transport.close()

        self._handle_event(Event("disconnect", self.server, "", [message]))


class AioReactor(Reactor):
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
        self.loop.run_forever()


class AioSimpleIRCClient(SimpleIRCClient):
    reactor_class = AioReactor
