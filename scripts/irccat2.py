#! /usr/bin/env python
#
# Example program using irc.client.
#
# This program is free without restrictions; do anything you like with
# it.
#
# Joel Rosdahl <joel@rosdahl.net>

import irc.client
import sys


class IRCCat(irc.client.SimpleIRCClient):
    def __init__(self, target):
        irc.client.SimpleIRCClient.__init__(self)
        self.target = target

    def on_welcome(self, connection, event):
        if irc.client.is_channel(self.target):
            connection.join(self.target)
        else:
            self.send_it()

    def on_join(self, connection, event):
        self.send_it()

    def on_disconnect(self, connection, event):
        sys.exit(0)

    def send_it(self):
        while 1:
            line = sys.stdin.readline().strip()
            if not line:
                break
            self.connection.privmsg(self.target, line)
        self.connection.quit("Using irc.client.py")


def main():
    if len(sys.argv) != 4:
        print("Usage: irccat2 <server[:port]> <nickname> <target>")
        print("\ntarget is a nickname or a channel.")
        sys.exit(1)

    s = sys.argv[1].split(":", 1)
    server = s[0]
    if len(s) == 2:
        try:
            port = int(s[1])
        except ValueError:
            print("Error: Erroneous port.")
            sys.exit(1)
    else:
        port = 6667
    nickname = sys.argv[2]
    target = sys.argv[3]

    c = IRCCat(target)
    try:
        c.connect(server, port, nickname)
    except irc.client.ServerConnectionError as x:
        print(x)
        sys.exit(1)
    c.start()


if __name__ == "__main__":
    main()
