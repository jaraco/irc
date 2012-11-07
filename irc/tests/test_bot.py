import irc.bot

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
