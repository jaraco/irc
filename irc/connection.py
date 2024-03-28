import socket


def identity(x):
    return x


class Factory:
    """
    A class for creating custom socket connections.

    To create a simple connection:

    .. code-block:: python

       server_address = ('localhost', 80)
       Factory()(server_address)

    To create an SSL connection:

    .. code-block:: python

       context = ssl.create_default_context()
       wrapper = functools.partial(context.wrap_socket, server_hostname=server_address)
       Factory(wrapper=ssl.wrap_socket)(server_address)

    To create an SSL connection with parameters to wrap_socket:

    .. code-block:: python

       context = ssl.create_default_context()
       wrapper = functools.partial(context.wrap_socket, server_hostname=server_address, ssl_cert=get_cert())
       Factory(wrapper=wrapper)(server_address)

    To create an IPv6 connection:

    .. code-block:: python

       Factory(ipv6=True)(server_address)

    Note that Factory doesn't save the state of the socket itself. The
    caller must do that, as necessary. As a result, the Factory may be
    re-used to create new connections with the same settings.

    """

    family = socket.AF_INET

    def __init__(self, bind_address=None, wrapper=identity, ipv6=False):
        self.bind_address = bind_address
        self.wrapper = wrapper
        if ipv6:
            self.family = socket.AF_INET6

    def connect(self, server_address):
        sock = self.wrapper(socket.socket(self.family, socket.SOCK_STREAM))
        self.bind_address and sock.bind(self.bind_address)
        sock.connect(server_address)
        return sock

    __call__ = connect


class AioFactory:
    """
    A class for creating async custom socket connections.

    To create a simple connection:

    .. code-block:: python

       server_address = ('localhost', 80)
       Factory()(protocol_instance, server_address)

    To create an SSL connection:

    .. code-block:: python

       Factory(ssl=True)(protocol_instance, server_address)

    To create an IPv6 connection:

    .. code-block:: python

       Factory(ipv6=True)(protocol_instance, server_address)

    Note that Factory doesn't save the state of the socket itself. The
    caller must do that, as necessary. As a result, the Factory may be
    re-used to create new connections with the same settings.

    """

    def __init__(self, **kwargs):
        self.connection_args = kwargs

    def connect(self, protocol_instance, server_address):
        return protocol_instance.loop.create_connection(
            lambda: protocol_instance, *server_address, **self.connection_args
        )

    __call__ = connect
