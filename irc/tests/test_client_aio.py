import asyncio
import contextlib
import warnings
from unittest.mock import MagicMock

import pytest

from irc import client_aio


def make_mocked_create_connection(mock_transport, mock_protocol):
    async def mock_create_connection(*args, **kwargs):
        return (mock_transport, mock_protocol)

    return mock_create_connection


@contextlib.contextmanager
def suppress_issue_197():
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', 'There is no current event loop')
        yield


def test_privmsg_sends_msg():
    # create dummy transport, protocol
    mock_transport = MagicMock()
    mock_protocol = MagicMock()

    # connect to dummy server
    with suppress_issue_197():
        loop = asyncio.get_event_loop()
    loop.create_connection = make_mocked_create_connection(
        mock_transport, mock_protocol
    )
    server = client_aio.AioReactor(loop=loop).server()
    loop.run_until_complete(server.connect('foo', 6667, 'my_irc_nick'))
    server.privmsg('#best-channel', 'You are great')

    mock_transport.write.assert_called_with(b'PRIVMSG #best-channel :You are great\r\n')

    loop.close()


def test_dcc_connection_connect():
    mock_transport = MagicMock()
    mock_protocol = MagicMock()

    loop = asyncio.new_event_loop()
    loop.create_connection = make_mocked_create_connection(
        mock_transport, mock_protocol
    )
    reactor = client_aio.AioReactor(loop=loop)
    dcc = reactor.dcc()
    loop.run_until_complete(dcc.connect('127.0.0.1', 12345))

    assert dcc.connected
    assert dcc.transport is mock_transport
    assert dcc.protocol is mock_protocol
    assert dcc.peeraddress == '127.0.0.1'
    assert dcc.peerport == 12345

    loop.close()


def test_dcc_connection_disconnect():
    mock_transport = MagicMock()
    mock_protocol = MagicMock()

    loop = asyncio.new_event_loop()
    loop.create_connection = make_mocked_create_connection(
        mock_transport, mock_protocol
    )
    reactor = client_aio.AioReactor(loop=loop)
    dcc = reactor.dcc()
    loop.run_until_complete(dcc.connect('127.0.0.1', 12345))
    dcc.disconnect('test message')

    mock_transport.close.assert_called_once()
    assert dcc not in reactor.connections
    # Calling disconnect again should be a no-op (idempotent)
    dcc.disconnect('test message again')
    mock_transport.close.assert_called_once()

    loop.close()


def test_dcc_connection_send_bytes():
    mock_transport = MagicMock()
    mock_protocol = MagicMock()

    loop = asyncio.new_event_loop()
    loop.create_connection = make_mocked_create_connection(
        mock_transport, mock_protocol
    )
    reactor = client_aio.AioReactor(loop=loop)
    dcc = reactor.dcc()
    loop.run_until_complete(dcc.connect('127.0.0.1', 12345))
    dcc.send_bytes(b'hello')

    mock_transport.write.assert_called_with(b'hello')

    loop.close()


def test_dcc_connection_send_bytes_not_connected():
    loop = asyncio.new_event_loop()
    reactor = client_aio.AioReactor(loop=loop)
    dcc = reactor.dcc()
    # Should not raise when not connected
    dcc.send_bytes(b'hello')
    loop.close()


def test_dcc_connection_process_data_chat():
    mock_transport = MagicMock()
    mock_protocol = MagicMock()

    loop = asyncio.new_event_loop()
    loop.create_connection = make_mocked_create_connection(
        mock_transport, mock_protocol
    )
    reactor = client_aio.AioReactor(loop=loop)
    dcc = reactor.dcc('chat')
    loop.run_until_complete(dcc.connect('127.0.0.1', 12345))

    events = []
    reactor.add_global_handler('dccmsg', lambda c, e: events.append(e))
    dcc.process_data(b'hello\nworld\n')

    assert len(events) == 2
    assert events[0].arguments == [b'hello']
    assert events[1].arguments == [b'world']

    loop.close()


def test_dcc_connection_process_data_raw():
    mock_transport = MagicMock()
    mock_protocol = MagicMock()

    loop = asyncio.new_event_loop()
    loop.create_connection = make_mocked_create_connection(
        mock_transport, mock_protocol
    )
    reactor = client_aio.AioReactor(loop=loop)
    dcc = reactor.dcc('raw')
    loop.run_until_complete(dcc.connect('127.0.0.1', 12345))

    events = []
    reactor.add_global_handler('dccmsg', lambda c, e: events.append(e))
    dcc.process_data(b'rawdata')

    assert len(events) == 1
    assert events[0].arguments == [b'rawdata']

    loop.close()


def test_dcc_connection_listen():
    loop = asyncio.new_event_loop()

    async def mock_create_server(factory, *args, **kwargs):
        mock_server = MagicMock()
        mock_socket = MagicMock()
        mock_socket.getsockname.return_value = ('127.0.0.1', 54321)
        mock_server.sockets = [mock_socket]
        return mock_server

    loop.create_server = mock_create_server

    reactor = client_aio.AioReactor(loop=loop)
    dcc = reactor.dcc()
    loop.run_until_complete(dcc.listen())

    assert dcc.passive
    assert dcc.localaddress == '127.0.0.1'
    assert dcc.localport == 54321
    assert hasattr(dcc, 'server')

    loop.close()


def test_dcc_connection_listen_ipv6():
    import socket

    loop = asyncio.new_event_loop()
    calls = []

    async def mock_create_server(factory, *args, **kwargs):
        calls.append(kwargs)
        mock_server = MagicMock()
        mock_socket = MagicMock()
        mock_socket.getsockname.return_value = ('::1', 54321)
        mock_server.sockets = [mock_socket]
        return mock_server

    loop.create_server = mock_create_server

    reactor = client_aio.AioReactor(loop=loop)
    dcc = reactor.dcc()
    loop.run_until_complete(dcc.listen(ipv6=True))

    assert calls[0]['family'] == socket.AF_INET6
    assert dcc.localaddress == '::1'

    loop.close()


def test_dcc_connection_listen_specific_port():
    import socket

    loop = asyncio.new_event_loop()
    calls = []

    async def mock_create_server(factory, *args, **kwargs):
        calls.append(args)
        mock_server = MagicMock()
        mock_socket = MagicMock()
        mock_socket.getsockname.return_value = ('127.0.0.1', 12345)
        mock_server.sockets = [mock_socket]
        return mock_server

    loop.create_server = mock_create_server

    reactor = client_aio.AioReactor(loop=loop)
    dcc = reactor.dcc()
    loop.run_until_complete(dcc.listen(port=12345))

    expected_host = socket.gethostbyname(socket.gethostname())
    assert (expected_host, 12345) in calls
    assert dcc.localport == 12345

    loop.close()


def test_dcc_connection_listen_port_range():
    loop = asyncio.new_event_loop()
    calls = []

    async def mock_create_server(factory, *args, **kwargs):
        calls.append(args)
        if args[1] == 1024:
            raise OSError('Address in use')
        mock_server = MagicMock()
        mock_socket = MagicMock()
        mock_socket.getsockname.return_value = ('127.0.0.1', args[1])
        mock_server.sockets = [mock_socket]
        return mock_server

    loop.create_server = mock_create_server

    reactor = client_aio.AioReactor(loop=loop)
    dcc = reactor.dcc()
    loop.run_until_complete(dcc.listen(port=(1024, 1026)))

    assert len(calls) == 2  # 1024 fails, 1025 succeeds
    assert calls[0][1] == 1024
    assert calls[1][1] == 1025
    assert dcc.localport == 1025

    loop.close()


def test_dcc_connection_listen_port_list():
    loop = asyncio.new_event_loop()
    calls = []

    async def mock_create_server(factory, *args, **kwargs):
        calls.append(args)
        if args[1] == 8080:
            raise OSError('Address in use')
        mock_server = MagicMock()
        mock_socket = MagicMock()
        mock_socket.getsockname.return_value = ('127.0.0.1', args[1])
        mock_server.sockets = [mock_socket]
        return mock_server

    loop.create_server = mock_create_server

    reactor = client_aio.AioReactor(loop=loop)
    dcc = reactor.dcc()
    loop.run_until_complete(dcc.listen(port=[8080, 9090]))

    assert len(calls) == 2
    assert calls[0][1] == 8080
    assert calls[1][1] == 9090
    assert dcc.localport == 9090

    loop.close()


def test_dcc_connection_listen_port_range_all_fail():
    loop = asyncio.new_event_loop()

    async def mock_create_server(factory, *args, **kwargs):
        raise OSError('Address in use')

    loop.create_server = mock_create_server

    reactor = client_aio.AioReactor(loop=loop)
    dcc = reactor.dcc()

    import irc.client

    with pytest.raises(irc.client.DCCConnectionError):
        loop.run_until_complete(dcc.listen(port=(1024, 1025)))

    loop.close()


def test_dcc_connection_listen_and_accept():
    loop = asyncio.new_event_loop()

    async def mock_create_server(factory, *args, **kwargs):
        mock_server = MagicMock()
        mock_socket = MagicMock()
        mock_socket.getsockname.return_value = ('127.0.0.1', 54321)
        mock_server.sockets = [mock_socket]
        return mock_server

    loop.create_server = mock_create_server

    reactor = client_aio.AioReactor(loop=loop)
    dcc = reactor.dcc()
    loop.run_until_complete(dcc.listen())

    # Simulate a client connecting by calling connection_made on the protocol
    mock_transport = MagicMock()
    mock_transport.get_extra_info.return_value = ('192.168.1.1', 12345)

    events = []
    reactor.add_global_handler('dcc_connect', lambda c, e: events.append(e))

    # Create the protocol and simulate connection_made
    protocol = dcc.protocol_class(dcc, loop)
    protocol.connection_made(mock_transport)

    assert dcc.connected
    assert dcc.transport is mock_transport
    assert dcc.peeraddress == '192.168.1.1'
    assert dcc.peerport == 12345
    assert len(events) == 1
    assert events[0].type == 'dcc_connect'
    dcc.server.close.assert_called_once()

    loop.close()


def test_dcc_connection_disconnect_with_server():
    loop = asyncio.new_event_loop()

    async def mock_create_server(factory, *args, **kwargs):
        mock_server = MagicMock()
        mock_socket = MagicMock()
        mock_socket.getsockname.return_value = ('127.0.0.1', 54321)
        mock_server.sockets = [mock_socket]
        return mock_server

    loop.create_server = mock_create_server

    reactor = client_aio.AioReactor(loop=loop)
    dcc = reactor.dcc()
    loop.run_until_complete(dcc.listen())

    mock_transport = MagicMock()
    mock_transport.get_extra_info.return_value = ('192.168.1.1', 12345)
    protocol = dcc.protocol_class(dcc, loop)
    protocol.connection_made(mock_transport)

    dcc.disconnect('test message')

    assert dcc.server.close.call_count == 2  # once in connection_made, once in disconnect
    mock_transport.close.assert_called_once()
    assert dcc not in reactor.connections
    # Calling disconnect again should be a no-op (idempotent)
    dcc.disconnect('test message again')
    assert dcc.server.close.call_count == 2
    mock_transport.close.assert_called_once()

    loop.close()


def test_dcc_connection_connect_error():
    async def failing_create_connection(*args, **kwargs):
        raise OSError('connection refused')

    loop = asyncio.new_event_loop()
    loop.create_connection = failing_create_connection
    reactor = client_aio.AioReactor(loop=loop)
    dcc = reactor.dcc()

    import irc.client

    with pytest.raises(irc.client.DCCConnectionError):
        loop.run_until_complete(dcc.connect('127.0.0.1', 12345))

    loop.close()


def test_dcc_connection_privmsg_chat():
    mock_transport = MagicMock()
    mock_protocol = MagicMock()

    loop = asyncio.new_event_loop()
    loop.create_connection = make_mocked_create_connection(
        mock_transport, mock_protocol
    )
    reactor = client_aio.AioReactor(loop=loop)
    dcc = reactor.dcc('chat')
    loop.run_until_complete(dcc.connect('127.0.0.1', 12345))
    dcc.privmsg('hello')

    mock_transport.write.assert_called_with(b'hello\n')

    loop.close()


def test_dcc_connection_privmsg_raw():
    mock_transport = MagicMock()
    mock_protocol = MagicMock()

    loop = asyncio.new_event_loop()
    loop.create_connection = make_mocked_create_connection(
        mock_transport, mock_protocol
    )
    reactor = client_aio.AioReactor(loop=loop)
    dcc = reactor.dcc('raw')
    loop.run_until_complete(dcc.connect('127.0.0.1', 12345))
    dcc.privmsg('hello')

    mock_transport.write.assert_called_with(b'hello')

    loop.close()
