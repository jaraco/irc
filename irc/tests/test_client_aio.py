from unittest.mock import MagicMock
import asyncio

from irc import client_aio


def make_mocked_create_connection(mock_transport, mock_protocol):
    async def mock_create_connection(*args, **kwargs):
        return (mock_transport, mock_protocol)

    return mock_create_connection


def test_privmsg_sends_msg():
    # create dummy transport, protocol
    mock_transport = MagicMock()
    mock_protocol = MagicMock()

    # connect to dummy server
    loop = asyncio.get_event_loop()
    loop.create_connection = make_mocked_create_connection(
        mock_transport, mock_protocol
    )
    server = client_aio.AioReactor(loop=loop).server()
    loop.run_until_complete(server.connect('foo', 6667, 'my_irc_nick'))
    server.privmsg('#best-channel', 'You are great')

    mock_transport.write.assert_called_with(b'PRIVMSG #best-channel :You are great\r\n')

    loop.close()
