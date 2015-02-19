#! /usr/bin/env python
#
# Example program using irc.client.
#
# This program is free without restrictions; do anything you like with
# it.
#
# Joel Rosdahl <joel@rosdahl.net>

import os
import struct
import sys
import argparse
import subprocess

import irc.client
import jaraco.logging

class DCCSend(irc.client.SimpleIRCClient):
    def __init__(self, receiver, filename):
        irc.client.SimpleIRCClient.__init__(self)
        self.receiver = receiver
        self.filename = filename
        self.filesize = os.path.getsize(self.filename)
        self.file = open(filename, 'rb')
        self.sent_bytes = 0

    def on_welcome(self, connection, event):
        self.dcc = self.dcc_listen("raw")
        msg_parts = map(str, (
            'SEND',
            os.path.basename(self.filename),
            irc.client.ip_quad_to_numstr(self.dcc.localaddress),
            self.dcc.localport,
            self.filesize,
        ))
        msg = subprocess.list2cmdline(msg_parts)
        self.connection.ctcp("DCC", self.receiver, msg)

    def on_dcc_connect(self, connection, event):
        if self.filesize == 0:
            self.dcc.disconnect()
            return
        self.send_chunk()

    def on_dcc_disconnect(self, connection, event):
        print("Sent file %s (%d bytes)." % (self.filename, self.filesize))
        self.connection.quit()

    def on_dccmsg(self, connection, event):
        acked = struct.unpack("!I", event.arguments[0])[0]
        if acked == self.filesize:
            self.dcc.disconnect()
            self.connection.quit()
        elif acked == self.sent_bytes:
            self.send_chunk()

    def on_disconnect(self, connection, event):
        sys.exit(0)

    def on_nosuchnick(self, connection, event):
        print("No such nickname:", event.arguments[0])
        self.connection.quit()

    def send_chunk(self):
        data = self.file.read(1024)
        self.dcc.send_bytes(data)
        self.sent_bytes = self.sent_bytes + len(data)

def get_args():
    parser = argparse.ArgumentParser(
        description="Send <filename> to <receiver> via DCC and then exit.",
    )
    parser.add_argument('server')
    parser.add_argument('nickname')
    parser.add_argument('receiver', help="the nickname to receive the file")
    parser.add_argument('filename')
    parser.add_argument('-p', '--port', default=6667, type=int)
    jaraco.logging.add_arguments(parser)
    return parser.parse_args()

def main():
    args = get_args()
    jaraco.logging.setup(args)

    c = DCCSend(args.receiver, args.filename)
    try:
        c.connect(args.server, args.port, args.nickname)
    except irc.client.ServerConnectionError as x:
        print(x)
        sys.exit(1)
    c.start()

if __name__ == "__main__":
    main()
