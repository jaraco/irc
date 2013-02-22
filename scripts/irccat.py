#! /usr/bin/env python
#
# Example program using irc.client.
#
# This program is free without restrictions; do anything you like with
# it.
#
# Joel Rosdahl <joel@rosdahl.net>

import argparse
import irc.client
import sys

target = None
"The nick or channel to which to send messages"

def on_connect(connection, event):
    if irc.client.is_channel(target):
        connection.join(target)
    else:
        while 1:
            line = sys.stdin.readline().strip()
            if not line:
                break
            connection.privmsg(target, line)
        connection.quit("Using irc.client.py")

def on_join(connection, event):
    while 1:
        line = sys.stdin.readline().strip()
        if not line:
            break
        connection.privmsg(target, line)
    connection.quit("Using irc.client.py")

def on_disconnect(connection, event):
    raise SystemExit()

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('server')
    parser.add_argument('nickname')
    parser.add_argument('target', help="a nickname or channel")
    parser.add_argument('-p', '--port', default=6667, type=int)
    return parser.parse_args()

def main():
    global target

    args = get_args()
    target = args.target

    client = irc.client.IRC()
    try:
        c = client.server().connect(args.server, args.port, args.nickname)
    except irc.client.ServerConnectionError:
        print(sys.exc_info()[1])
        raise SystemExit(1)

    c.add_global_handler("welcome", on_connect)
    c.add_global_handler("join", on_join)
    c.add_global_handler("disconnect", on_disconnect)

    client.process_forever()

if __name__ == '__main__':
    main()
