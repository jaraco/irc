#! /usr/bin/env python
#
# Example program using ircbot.py.
#
# Joel Rosdahl <joel@rosdahl.net>

"""A simple example bot.

This is an example bot that uses the SingleServerIRCBot class from
ircbot.py.  The bot enters a channel and listens for commands in
private messages or channel traffic.  Commands in channel messages are
given by prefixing the text by the bot name followed by a colon.

The known commands are:

    stats -- Prints some channel information.

    disconnect -- Disconnect the bot.  The bot will try to reconnect
                  after 60 seconds.

    die -- Let the bot cease to exist.
"""

import string
from ircbot import SingleServerIRCBot
from irclib import nm_to_n, irc_lower

class TestBot(SingleServerIRCBot):
    def __init__(self, channel, nickname, server, port=6667):
        SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel = channel
        self.start()

    def on_welcome(self, c, e):
        c.join(self.channel)

    def on_privmsg(self, c, e):
        self.do_command(nm_to_n(e.source()), e.arguments()[0])

    def on_pubmsg(self, c, e):
        a = string.split(e.arguments()[0], ":", 1)
        if len(a) > 1 and irc_lower(a[0]) == irc_lower(self.connection.get_nickname()):
            self.do_command(nm_to_n(e.source()), string.strip(a[1]))
        return

    def do_command(self, nick, cmd):
        c = self.connection

        if cmd == "disconnect":
            self.disconnect()
        elif cmd == "die":
            self.die()
        elif cmd == "stats":
            for chname, chobj in self.channels.items():
                c.notice(nick, "--- Channel statistics ---")
                c.notice(nick, "Channel: " + chname)
                users = chobj.users()
                users.sort()
                c.notice(nick, "Users: " + string.join(users, ", "))
                opers = chobj.opers()
                opers.sort()
                c.notice(nick, "Opers: " + string.join(opers, ", "))
                voiced = chobj.voiced()
                voiced.sort()
                c.notice(nick, "Voiced: " + string.join(voiced, ", "))
        else:
            c.notice(nick, "Not understood: " + cmd)

def main():
    import sys
    if len(sys.argv) != 4:
        print "Usage: testbot <server[:port]> <channel> <nickname>"
        sys.exit(1)

    s = string.split(sys.argv[1], ":", 1)
    server = s[0]
    if len(s) == 2:
        try:
            port = int(s[1])
        except ValueError:
            print "Error: Erroneous port."
            sys.exit(1)
    else:
        port = 6667
    channel = sys.argv[2]
    nickname = sys.argv[3]

    bot = TestBot(channel, nickname, server, port)
    bot.start()

if __name__ == "__main__":
    main()
