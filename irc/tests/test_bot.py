import time
import threading

import six

import pytest

import irc.client
import irc.bot
import irc.server
from irc.bot import ServerSpec


class TestServerSpec(object):

    def test_with_host(self):
        server_spec = ServerSpec('irc.example.com')
        assert server_spec.host == 'irc.example.com'
        assert server_spec.port == 6667
        assert server_spec.password is None

    def test_with_host_and_port(self):
        server_spec = ServerSpec('irc.example.org', port=6669)
        assert server_spec.host == 'irc.example.org'
        assert server_spec.port == 6669
        assert server_spec.password is None

    def test_with_host_and_password(self):
        server_spec = ServerSpec('irc.example.net', password='heres johnny!')
        assert server_spec.host == 'irc.example.net'
        assert server_spec.port == 6667
        assert server_spec.password == 'heres johnny!'

    def test_with_host_and_port_and_password(self):
        server_spec = ServerSpec(
            'irc.example.gov', port=6668, password='there-is-only-zuul')
        assert server_spec.host == 'irc.example.gov'
        assert server_spec.port == 6668
        assert server_spec.password == 'there-is-only-zuul'


class TestChannel(object):

    def test_add_remove_nick(self):
        channel = irc.bot.Channel()
        channel.add_user('tester1')
        channel.remove_user('tester1')
        assert 'tester1' not in channel.users()
        channel.add_user('tester1')
        assert 'tester1' in channel.users()

    def test_change_nick(self):
        channel = irc.bot.Channel()
        channel.add_user('tester1')
        channel.change_nick('tester1', 'was_tester')

    def test_has_user(self):
        channel = irc.bot.Channel()
        channel.add_user('tester1')
        assert channel.has_user('Tester1')

    def test_set_mode_clear_mode(self):
        channel = irc.bot.Channel()
        channel.add_user('tester1')
        channel.set_mode('o', 'tester1')
        assert channel.is_oper('tester1')
        channel.clear_mode('o', 'tester1')
        assert not channel.is_oper('tester1')

    def test_remove_add_clears_mode(self):
        channel = irc.bot.Channel()
        channel.add_user('tester1')
        channel.set_mode('v', 'tester1')
        assert channel.is_voiced('tester1')
        channel.remove_user('tester1')
        channel.add_user('tester1')
        assert not channel.is_voiced('tester1')


class DisconnectHandler(irc.server.IRCClient):
    """
    Immediately disconnect the client after connecting
    """
    def handle(self):
        self.request.close()


@pytest.yield_fixture
def disconnecting_server():
    """
    An IRC server that disconnects the client immediately.
    """
    # bind to localhost on an ephemeral port
    bind_address = '127.0.0.1', 0
    try:
        srv = irc.server.IRCServer(bind_address, DisconnectHandler)
        threading.Thread(target=srv.serve_forever).start()
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


class TestBot(object):
    def test_construct_bot(self):
        bot = irc.bot.SingleServerIRCBot(
            server_list=[('localhost', '9999')],
            realname='irclibbot',
            nickname='irclibbot',
        )
        assert len(bot.server_list) == 1
        svr = bot.server_list[0]
        assert svr.host == 'localhost'
        assert svr.port == '9999'
        assert svr.password is None

    def test_namreply_no_channel(self):
        """
        If channel is '*', _on_namreply should not crash.

        Regression test for #22
        """
        event = irc.client.Event(
            type=None, source=None, target=None,
            arguments=['*', '*', 'nick'])
        _on_namreply = six.get_unbound_function(
            irc.bot.SingleServerIRCBot._on_namreply)
        _on_namreply(None, None, event)

    def test_reconnects_are_stable(self, disconnecting_server):
        """
        Ensure that disconnects from the server don't lead to
        exponential growth in reconnect attempts.
        """
        recon = irc.bot.ExponentialBackoff(min_interval=0.01)
        bot = irc.bot.SingleServerIRCBot(
            server_list=[disconnecting_server.socket.getsockname()],
            realname='reconnect_test',
            nickname='reconnect_test',
            recon=recon,
        )
        bot._connect()
        for x in range(4):
            bot.reactor.process_once()
            time.sleep(0.01)
        assert len(bot.reactor.scheduler.queue) <= 1
