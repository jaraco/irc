#! /usr/bin/env python
#
# Example program using irc.client_aio.
#
# This program demonstrates DCC CHAT using the asyncio-based client.
#
# This program is free without restrictions; do anything you like with
# it.

import argparse
import shlex

import jaraco.logging

import irc.client
import irc.client_aio


class DCCChat(irc.client_aio.AioSimpleIRCClient):
    def __init__(self, target=None):
        super().__init__()
        self.target = target
        self.dcc = None

    def on_welcome(self, connection, event):
        if self.target:
            self.dcc = self.dcc_listen('chat')
            msg_parts = [
                'CHAT',
                'chat',
                irc.client.ip_quad_to_numstr(self.dcc.localaddress),
                self.dcc.localport,
            ]
            msg = ' '.join(map(str, msg_parts))
            connection.ctcp('DCC', self.target, msg)
            print(f"Listening for DCC CHAT from {self.target} on port {self.dcc.localport}")
        else:
            print("Waiting for incoming DCC CHAT requests...")

    def on_ctcp(self, connection, event):
        payload = event.arguments[1]
        parts = shlex.split(payload)
        if len(parts) < 4 or parts[0] != 'CHAT':
            return
        command, dcctype, peer_address, peer_port = parts[:4]
        peer_address = irc.client.ip_numstr_to_quad(peer_address)
        peer_port = int(peer_port)
        print(f"Received DCC CHAT request from {event.source}: {peer_address}:{peer_port}")
        self.dcc = self.dcc_connect(peer_address, peer_port, 'chat')

    def on_dcc_connect(self, connection, event):
        print("DCC CHAT connected.")
        if self.target:
            connection.privmsg("Hello! This is an asyncio DCC CHAT echo bot.")

    def on_dcc_disconnect(self, connection, event):
        print("DCC CHAT disconnected.")
        self.connection.quit()

    def on_dccmsg(self, connection, event):
        text = event.arguments[0].decode('utf-8', errors='replace').rstrip('\n')
        print(f"< {text}")
        response = f"Echo: {text}"
        print(f"> {response}")
        connection.privmsg(response)

    def on_disconnect(self, connection, event):
        raise SystemExit()


def get_args():
    parser = argparse.ArgumentParser(
        description="Connect to an IRC server and use DCC CHAT."
    )
    parser.add_argument('server')
    parser.add_argument('nickname')
    parser.add_argument(
        '-t', '--target', default=None,
        help="Nickname to send a DCC CHAT request to (omit to wait for requests)"
    )
    parser.add_argument('-p', '--port', default=6667, type=int)
    jaraco.logging.add_arguments(parser)
    return parser.parse_args()


def main():
    args = get_args()
    jaraco.logging.setup(args)

    client = DCCChat(target=args.target)
    client.connect(args.server, args.port, args.nickname)
    client.start()


if __name__ == '__main__':
    main()
