#! /usr/bin/env python
#
# Example program using irc.client.
#
# This program is free without restrictions; do anything you like with
# it.
#
# Joel Rosdahl <joel@rosdahl.net>

from __future__ import print_function

import os
import struct
import sys
import argparse
import shlex

import jaraco.logging

import irc.client

class DCCReceive(irc.client.SimpleIRCClient):
    def __init__(self):
        irc.client.SimpleIRCClient.__init__(self)
        self.received_bytes = 0

    def on_ctcp(self, connection, event):
        payload = event.arguments[1]
        parts = shlex.split(payload)
        command, filename, peer_address, peer_port, size = parts
        if command != "SEND":
            return
        self.filename = os.path.basename(filename)
        if os.path.exists(self.filename):
            print("A file named", self.filename,
                "already exists. Refusing to save it.")
            self.connection.quit()
            return
        self.file = open(self.filename, "wb")
        peer_address = irc.client.ip_numstr_to_quad(peer_address)
        peer_port = int(peer_port)
        self.dcc = self.dcc_connect(peer_address, peer_port, "raw")

    def on_dccmsg(self, connection, event):
        data = event.arguments[0]
        self.file.write(data)
        self.received_bytes = self.received_bytes + len(data)
        self.dcc.send_bytes(struct.pack("!I", self.received_bytes))

    def on_dcc_disconnect(self, connection, event):
        self.file.close()
        print("Received file %s (%d bytes)." % (self.filename,
                                                self.received_bytes))
        self.connection.quit()

    def on_disconnect(self, connection, event):
        sys.exit(0)

def get_args():
    parser = argparse.ArgumentParser(
        description="Receive a single file to the current directory via DCC "
            "and then exit.",
    )
    parser.add_argument('server')
    parser.add_argument('nickname')
    parser.add_argument('-p', '--port', default=6667, type=int)
    jaraco.logging.add_arguments(parser)
    return parser.parse_args()

def main():
    args = get_args()
    jaraco.logging.setup(args)

    c = DCCReceive()
    try:
        c.connect(args.server, args.port, args.nickname)
    except irc.client.ServerConnectionError as x:
        print(x)
        sys.exit(1)
    c.start()

if __name__ == "__main__":
    main()
