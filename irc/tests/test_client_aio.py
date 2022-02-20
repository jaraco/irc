import warnings
import contextlib
from unittest.mock import MagicMock
import asyncio

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
