#! /usr/bin/env python
#
# Example program using irclib.py.
#
# This program is free without restrictions; do anything you like with
# it.
#
# Joel Rosdahl <joel@rosdahl.net>

import irclib
import string
import sys

def on_connect(connection, event):
    if irclib.is_channel(target):
        connection.join(target)
    else:
        while 1:
            line = sys.stdin.readline()
            if not line:
                break
            connection.privmsg(target, line)
        connection.quit("Using irclib.py")

def on_join(connection, event):
    while 1:
        line = sys.stdin.readline()
        if not line:
            break
        connection.privmsg(target, line)
    connection.quit("Using irclib.py")

if len(sys.argv) != 4:
    print "Usage: irccat <server[:port]> <nickname> <target>"
    print "\ntarget is a nickname or a channel."
    sys.exit(1)

def on_disconnect(connection, event):
    sys.exit(0)

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
nickname = sys.argv[2]
target = sys.argv[3]

irc = irclib.IRC()
try:
    c = irc.server().connect(server, port, nickname)
except irclib.ServerConnectionError, x:
    print x
    sys.exit(1)

c.add_global_handler("welcome", on_connect)
c.add_global_handler("join", on_join)
c.add_global_handler("disconnect", on_disconnect)

irc.process_forever()
