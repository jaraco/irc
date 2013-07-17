
import six

import irc.client
import irc.bot
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
        server_spec = ServerSpec('irc.example.gov', port=6668, password='there-is-only-zuul')
        assert server_spec.host == 'irc.example.gov'
        assert server_spec.port == 6668
        assert server_spec.password == 'there-is-only-zuul'

class TestChannel(object):

    def test_add_remove_nick(self):
        channel = irc.bot.Channel()
        channel.add_user('tester1')
        channel.remove_user('tester1')
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

class TestBot(object):
    def test_construct_bot(self):
        bot = irc.bot.SingleServerIRCBot(
            server_list = [('localhost', '9999')],
            realname = 'irclibbot',
            nickname = 'irclibbot',
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
        event = irc.client.Event(type=None, source=None, target=None,
            arguments=['*', '*', 'nick'])
        _on_namreply = six.get_unbound_function(
            irc.bot.SingleServerIRCBot._on_namreply)
        _on_namreply(None, None, event)
