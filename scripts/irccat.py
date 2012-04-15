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

def on_connect(connection, event):
    if irc.client.is_channel(target):
        connection.join(target)
    else:
        while 1:
            line = sys.stdin.readline()
            if not line:
                break
            connection.privmsg(target, line)
        connection.quit("Using irc.client.py")

def on_join(connection, event):
    while 1:
        line = sys.stdin.readline()
        if not line:
            break
        connection.privmsg(target, line)
    connection.quit("Using irc.client.py")

def on_disconnect(connection, event):
    raise SystemExit()

def main():
    global target
    if len(sys.argv) != 4:
        print "Usage: irccat <server[:port]> <nickname> <target>"
        print "\ntarget is a nickname or a channel."
        raise SystemExit(1)

    cmd, host_port, nickname, target = sys.argv

    s = host_port.split(":", 1)
    server = s[0]
    if len(s) == 2:
        try:
            port = int(s[1])
        except ValueError:
            print "Error: Erroneous port."
            raise SystemExit(1)
    else:
        port = 6667

    client = irc.client.IRC()
    try:
        c = client.server().connect(server, port, nickname)
    except irc.client.ServerConnectionError, x:
        print x
        raise SystemExit(1)

    c.add_global_handler("welcome", on_connect)
    c.add_global_handler("join", on_join)
    c.add_global_handler("disconnect", on_disconnect)

    client.process_forever()

if __name__ == '__main__':
    main()
