#!/usr/bin/env python
#
# Example program using irc.client_aio.
#
# Active DCC file receiver: connects to an IRC server, joins a channel,
# sends "!send <filename>" to a target nick, receives the CTCP DCC SEND
# reply, actively connects to the sender, and saves the file.

import argparse
import asyncio
import os
import shlex
import struct
import sys

import jaraco.logging

import irc.client
import irc.client_aio


class DCCReceiveAio:
    def __init__(self, loop, server, port, nickname, channel, target, filename):
        self.loop = loop
        self.server = server
        self.port = port
        self.nickname = nickname
        self.channel = channel
        self.target = target
        self.filename = filename

        self.reactor = irc.client_aio.AioReactor(loop=loop)
        self.conn = self.reactor.server()
        self.dcc = None
        self.file = None
        self.received_bytes = 0

    async def run(self):
        await self.conn.connect(self.server, self.port, self.nickname)
        self.conn.add_global_handler("welcome", self.on_welcome)
        self.conn.add_global_handler("ctcp", self.on_ctcp)
        self.conn.add_global_handler("dccmsg", self.on_dccmsg)
        self.conn.add_global_handler("dcc_disconnect", self.on_dcc_disconnect)
        self.conn.add_global_handler("disconnect", self.on_disconnect)

        self.reactor.process_forever()

    def on_welcome(self, connection, event):
        connection.join(self.channel)
        connection.privmsg(self.target, f"!send {self.filename}")

    def on_ctcp(self, connection, event):
        payload = event.arguments[1]
        parts = shlex.split(payload)
        if len(parts) < 5:
            return
        command, filename, peer_address, peer_port, size = parts
        if command != "SEND":
            return

        save_name = os.path.basename(filename)
        if os.path.exists(save_name):
            print("A file named", save_name, "already exists. Refusing to save it.")
            self.conn.quit()
            return

        self.file = open(save_name, "wb")
        self.received_bytes = 0

        peer_address = irc.client.ip_numstr_to_quad(peer_address)
        peer_port = int(peer_port)

        self.reactor.loop.create_task(self._do_connect(peer_address, peer_port))

    async def _do_connect(self, peer_address, peer_port):
        self.dcc = self.reactor.dcc("raw")
        await self.dcc.connect(peer_address, peer_port)
        print(f"Connected to {peer_address}:{peer_port} for DCC receive")

    def on_dccmsg(self, connection, event):
        data = event.arguments[0]
        self.file.write(data)
        self.received_bytes += len(data)
        self.dcc.send_bytes(struct.pack("!I", self.received_bytes))

    def on_dcc_disconnect(self, connection, event):
        self.file.close()
        print(f"Received file {os.path.basename(self.filename)} ({self.received_bytes} bytes)")
        self.conn.quit()

    def on_disconnect(self, connection, event):
        raise SystemExit()


def get_args():
    parser = argparse.ArgumentParser(
        description="Asyncio DCC file receiver. Joins a channel, requests "
        "a file from a nick, and saves it."
    )
    parser.add_argument('server')
    parser.add_argument('nickname')
    parser.add_argument('channel')
    parser.add_argument('target', help="Nickname of the sender")
    parser.add_argument('filename', help="File to request")
    parser.add_argument(
        '-p', '--port', default=6667, type=int, help="IRC server port"
    )
    jaraco.logging.add_arguments(parser)
    return parser.parse_args()


def main():
    args = get_args()
    jaraco.logging.setup(args)

    loop = asyncio.new_event_loop()
    client = DCCReceiveAio(
        loop, args.server, args.port, args.nickname,
        args.channel, args.target, args.filename
    )

    try:
        loop.run_until_complete(client.run())
    except irc.client.ServerConnectionError:
        print(sys.exc_info()[1])
        raise SystemExit(1) from None
    finally:
        loop.close()


if __name__ == '__main__':
    main()
