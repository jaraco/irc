#! /usr/bin/env python
#
# Example program using irc.client.
#
# This program is free without restrictions; do anything you like with
# it.

import sys
import argparse
import itertools
import asyncio

import irc.client_aio
import irc.client
import jaraco.logging

target = None


def on_connect(connection, event):
    if irc.client.is_channel(target):
        connection.join(target)
        return


def on_join(connection, event):
    connection.read_loop = asyncio.ensure_future(
        main_loop(connection), loop=connection.reactor.loop
    )


def get_lines():
    while True:
        yield sys.stdin.readline().strip()


async def main_loop(connection):
    for line in itertools.takewhile(bool, get_lines()):
        connection.privmsg(target, line)

        # Allow pause in the stdin loop to not block the asyncio event loop
        asyncio.sleep(0)
    connection.quit("Using irc.client_aio.py")


def on_disconnect(connection, event):
    raise SystemExit()


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
    global target

    args = get_args()
    jaraco.logging.setup(args)
    target = args.target

    loop = asyncio.get_event_loop()
    reactor = irc.client_aio.AioReactor(loop=loop)

    try:
        c = loop.run_until_complete(reactor.server().connect(
            args.server, args.port, args.nickname, password=args.password
        ))
    except irc.client.ServerConnectionError:
        print(sys.exc_info()[1])
        raise SystemExit(1)

    except irc.client.ServerConnectionError:
        print(sys.exc_info()[1])
        raise SystemExit(1)

    c.add_global_handler("welcome", on_connect)
    c.add_global_handler("join", on_join)
    c.add_global_handler("disconnect", on_disconnect)

    try:
        reactor.process_forever()
    finally:
        loop.close()


if __name__ == '__main__':
    main()
