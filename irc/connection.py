from __future__ import absolute_import

import socket
import importlib

identity = lambda x: x

class Factory(object):
    """
    A class for creating custom socket connections.

    To create a simple connection:

        server_address = ('localhost', 80)
        Factory()(server_address)

    To create an SSL connection:

        Factory(wrapper=ssl.wrap_socket)(server_address)

    To create an SSL connection with parameters to wrap_socket:

        wrapper = functools.partial(ssl.wrap_socket, ssl_cert=get_cert())
        Factory(wrapper=wrapper)(server_address)

    To create an IPv6 connection:

        Factory(ipv6=True)(server_address)

    Note that Factory doesn't save the state of the socket itself. The
    caller must do that, as necessary. As a result, the Factory may be
    re-used to create new connections with the same settings.

    """

    family = socket.AF_INET

    def __init__(self, bind_address=('', 0), wrapper=identity, ipv6=False):
        self.bind_address = bind_address
        self.wrapper = wrapper
        if ipv6:
            self.family = socket.AF_INET6

    def from_legacy_params(self, localaddress='', localport=0, ssl=False,
            ipv6=False):
        if localaddress or localport:
            self.bind_address = (localaddress, localport)
        if ssl:
            self.wrapper = importlib.import_module('ssl').wrap_socket
        if ipv6:
            self.family = socket.AF_INET6

    def connect(self, server_address):
        sock = self.wrapper(socket.socket(self.family, socket.SOCK_STREAM))
        sock.bind(self.bind_address)
        sock.connect(server_address)
        return sock
    __call__ = connect
