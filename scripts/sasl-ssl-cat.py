#! /usr/bin/env python3
#
# Example program using irc.client.
#
# This program is free without restrictions; do anything you like with
# it.
# IMPORTANT: sasl_login must equal your nickserv account name
# 
# Matthew Blau <mrb1105@gmail.com>

import functools
import ssl
import sys

import irc.client
import irc


class IRCCat(irc.client.SimpleIRCClient):
    def __init__(self, target):
        irc.client.SimpleIRCClient.__init__(self)
        self.target = target

    def on_welcome(self, connection, event):
        if irc.client.is_channel(self.target):
            connection.join(self.target)
        else:
            self.send_it()

    def on_login_failed(self, connection, event):
        print(event)


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
    server ="irc.libera.chat"
    port = 6697
    nickname = "nickname"
    account_name="username"
    target = "##channel"
    password = ""

    c = IRCCat(target)
    try:
        context = ssl.create_default_context()
        wrapper = functools.partial(context.wrap_socket, server_hostname=server)

        c.connect(server, port, nickname, password,sasl_login=account_name, username=account_name, connect_factory=irc.connection.Factory(wrapper=wrapper))
    except irc.client.ServerConnectionError as x:
        print(x)
        sys.exit(1)
    c.start()


if __name__ == "__main__":
    main()