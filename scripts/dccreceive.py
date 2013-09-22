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

import irc.client
import irc.logging

class DCCReceive(irc.client.SimpleIRCClient):
    def __init__(self):
        irc.client.SimpleIRCClient.__init__(self)
        self.received_bytes = 0

    def on_ctcp(self, connection, event):
        args = event.arguments[1].split()
        if args[0] != "SEND":
            return
        self.filename = os.path.basename(args[1])
        if os.path.exists(self.filename):
            print("A file named", self.filename,)
            print("already exists. Refusing to save it.")
            self.connection.quit()
        self.file = open(self.filename, "wb")
        peeraddress = irc.client.ip_numstr_to_quad(args[2])
        peerport = int(args[3])
        self.dcc = self.dcc_connect(peeraddress, peerport, "raw")

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
    irc.logging.add_arguments(parser)
    return parser.parse_args()

def main():
    args = get_args()
    irc.logging.setup(args)

    c = DCCReceive()
    try:
        c.connect(args.server, args.port, args.nickname)
    except irc.client.ServerConnectionError as x:
        print(x)
        sys.exit(1)
    c.start()

if __name__ == "__main__":
    main()
