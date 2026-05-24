#!/usr/bin/env python
#
# Example program using irc.client_aio.
#
# Passive DCC file sender: connects to an IRC server, joins a channel,
# and waits for someone to type "!send <filename>".  It then listens
# for an incoming DCC connection and sends the file.
#
# Supports a specific port (--port 8080) or a port range fallback
# (--port 1024-65535, the default when --port is omitted).

import argparse
import asyncio
import os
import struct
import sys

import jaraco.logging

import irc.client
import irc.client_aio


class DCCSendAio:
    def __init__(self, loop, server, port, nickname, channel, port_arg=None):
        self.loop = loop
        self.server = server
        self.port = port
        self.nickname = nickname
        self.channel = channel
        self.port_arg = port_arg

        self.reactor = irc.client_aio.AioReactor(loop=loop)
        self.conn = self.reactor.server()
        self.dcc = None
        self.file = None
        self.filesize = 0
        self.sent_bytes = 0
        self.filename = None

    async def run(self):
        await self.conn.connect(self.server, self.port, self.nickname)
        self.conn.add_global_handler("welcome", self.on_welcome)
        self.conn.add_global_handler("privmsg", self.on_privmsg)
        self.conn.add_global_handler("dcc_connect", self.on_dcc_connect)
        self.conn.add_global_handler("dccmsg", self.on_dccmsg)
        self.conn.add_global_handler("dcc_disconnect", self.on_dcc_disconnect)
        self.conn.add_global_handler("disconnect", self.on_disconnect)

        self.reactor.process_forever()

    def on_welcome(self, connection, event):
        connection.join(self.channel)

    def on_privmsg(self, connection, event):
        nick = irc.client.NickMask(event.source).nick
        text = event.arguments[0]

        if not text.startswith("!send "):
            return

        filename = text[6:].strip()
        if not os.path.exists(filename):
            connection.privmsg(nick, f"File not found: {filename}")
            return

        self.filename = filename
        self.reactor.loop.create_task(self._start_send(nick))

    async def _start_send(self, receiver):
        self.file = open(self.filename, 'rb')
        self.filesize = os.path.getsize(self.filename)
        self.sent_bytes = 0

        self.dcc = self.reactor.dcc("raw")

        # Determine port: specific, range, or default range
        if self.port_arg is None:
            port = (1024, 65535)
        elif '-' in self.port_arg:
            min_port, max_port = map(int, self.port_arg.split('-'))
            port = (min_port, max_port)
        else:
            port = int(self.port_arg)

        await self.dcc.listen(port=port)

        ip_str = irc.client.ip_quad_to_numstr(self.dcc.localaddress)
        msg = f"SEND {os.path.basename(self.filename)} {ip_str} {self.dcc.localport} {self.filesize}"
        self.conn.ctcp("DCC", receiver, msg)

        print(f"Listening for DCC connection on {self.dcc.localaddress}:{self.dcc.localport}")

    def on_dcc_connect(self, connection, event):
        if self.filesize == 0:
            self.dcc.disconnect()
            return
        self._send_chunk()

    def _send_chunk(self):
        data = self.file.read(1024)
        self.dcc.send_bytes(data)
        self.sent_bytes += len(data)

    def on_dccmsg(self, connection, event):
        acked = struct.unpack("!I", event.arguments[0])[0]
        if acked == self.filesize:
            self.dcc.disconnect()
            self.conn.quit()
        elif acked == self.sent_bytes:
            self._send_chunk()

    def on_dcc_disconnect(self, connection, event):
        self.file.close()
        print(f"Sent file {self.filename} ({self.sent_bytes} bytes)")
        self.conn.quit()

    def on_disconnect(self, connection, event):
        raise SystemExit()


def get_args():
    parser = argparse.ArgumentParser(
        description="Asyncio DCC file sender. Waits for '!send <filename>' "
        "in a channel, then sends the file via DCC."
    )
    parser.add_argument('server')
    parser.add_argument('nickname')
    parser.add_argument('channel')
    parser.add_argument(
        '--port',
        default=None,
        help="Port to listen on. Can be a single port or a range "
        "like '1024-65535'. Default is to try 1024-65535.",
    )
    parser.add_argument(
        '-p', '--irc-port', default=6667, type=int, help="IRC server port"
    )
    jaraco.logging.add_arguments(parser)
    return parser.parse_args()


def main():
    args = get_args()
    jaraco.logging.setup(args)

    loop = asyncio.new_event_loop()
    client = DCCSendAio(
        loop, args.server, args.irc_port, args.nickname, args.channel, args.port
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
