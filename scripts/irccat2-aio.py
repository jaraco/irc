#! /usr/bin/env python
#
# Example program using irc.client.
#
# This program is free without restrictions; do anything you like with
# it.
import sys
import asyncio
import argparse

import irc.client
import irc.client_aio
import jaraco.logging


class AioIRCCat(irc.client_aio.AioSimpleIRCClient):
    def __init__(self, target):
        irc.client.SimpleIRCClient.__init__(self)
        self.target = target

    def on_welcome(self, connection, event):
        if irc.client.is_channel(self.target):
            connection.join(self.target)
        else:
            self.future = asyncio.ensure_future(
                self.send_it(), loop=connection.reactor.loop
            )

    def on_join(self, connection, event):
        self.future = asyncio.ensure_future(
            self.send_it(), loop=connection.reactor.loop
        )

    def on_disconnect(self, connection, event):
        self.future.cancel()
        sys.exit(0)

    async def send_it(self):
        while 1:
            line = sys.stdin.readline().strip()
            if not line:
                break
            self.connection.privmsg(self.target, line)

            # Allow pause in the stdin loop to not block asyncio loop
            asyncio.sleep(0)
        self.connection.quit("Using irc.client.py")


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('server')
    parser.add_argument('nickname')
    parser.add_argument('target', help="a nickname or channel")
    parser.add_argument('--password', default=None, help="optional password")
    parser.add_argument('-p', '--port', default=6667, type=int)
    jaraco.logging.add_arguments(parser)
    return parser.parse_args()


def main():
    args = get_args()
    jaraco.logging.setup(args)
    target = args.target

    c = AioIRCCat(target)

    try:
        c.connect(
            args.server, args.port, args.nickname, password=args.password
        )
    except irc.client.ServerConnectionError as x:
        sys.exit(1)

    try:
        c.start()
    finally:
        c.connection.disconnect()
        c.reactor.loop.close()


if __name__ == "__main__":
    main()
