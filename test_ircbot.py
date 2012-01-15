import ircbot

class TestChannel(object):

    def test_add_remove_nick(self):
        channel = ircbot.Channel()
        channel.add_user('tester1')
        channel.remove_user('tester1')
        channel.add_user('tester1')
        assert 'tester1' in channel.users()

    def test_change_nick(self):
        channel = ircbot.Channel()
        channel.add_user('tester1')
        channel.change_nick('tester1', 'was_tester')

    def test_has_user(self):
        channel = ircbot.Channel()
        channel.add_user('tester1')
        assert channel.has_user('Tester1')
