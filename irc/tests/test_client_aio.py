from unittest.mock import patch, MagicMock
import asyncio

from irc import client_aio


@patch('asyncio.base_events.BaseEventLoop.create_connection')
def test_privmsg_sends_msg(create_connection_mock):
    # create dummy transport, protocol
    fake_connection = asyncio.Future()

    mock_transport = MagicMock()
    mock_protocol = MagicMock()

    fake_connection.set_result((mock_transport, mock_protocol))
    create_connection_mock.return_value = fake_connection

    # connect to dummy server
    loop = asyncio.get_event_loop()
    server = client_aio.AioReactor(loop=loop).server()
    loop.run_until_complete(server.connect('foo', 6667, 'my_irc_nick'))
    server.privmsg('#best-channel', 'You are great')

    mock_transport.write.assert_called_with(b'PRIVMSG #best-channel :You are great\r\n')

    loop.close()
