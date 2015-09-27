#! /usr/bin/env python
#
# Example program using irc.client.
#
# This program is free without restrictions; do anything you like with
# it.
#
# Joel Rosdahl <joel@rosdahl.net>

import sys
import argparse
import itertools
import functools

import irc.client
import jaraco.logging

def get_lines():
    while True:
        yield sys.stdin.readline().strip()

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('server')
    parser.add_argument('nickname')
    parser.add_argument('target', help="a nickname or channel")
    parser.add_argument('-p', '--port', default=6667, type=int)
    jaraco.logging.add_arguments(parser)
    return parser.parse_args()

class Protocol(irc.client.Protocol):
    def on_welcome(self, event):
        assert irc.client.is_channel(self.target)
        self.join(self.target)

    def on_join(self, event):
        for line in itertools.takewhile(bool, get_lines()):
            print(line)
            self.privmsg(self.target, line)
        self.quit("Using irc.client.py")

def main():
    global target

    args = get_args()
    jaraco.logging.setup(args)

    proto_factory = functools.partial(Protocol,
        nickname=args.nickname,
        target=args.target,
    )
    import asyncio
    reactor = asyncio.SelectorEventLoop()
    connection = reactor.create_connection(proto_factory, args.server, args.port)

    transport, protocol = reactor.run_until_complete(connection)

    reactor.run_forever()

if __name__ == '__main__':
    main()
