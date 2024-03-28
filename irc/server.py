"""
irc.server

This server has basic support for:

* Connecting
* Channels
* Nicknames
* Public/private messages

It is MISSING support for notably:

* Server linking
* Modes (user and channel)
* Proper error reporting
* Basically everything else

It is mostly useful as a testing tool or perhaps for building something like a
private proxy on. Do NOT use it in any kind of production code or anything that
will ever be connected to by the public.

"""

#
# Very simple hacky ugly IRC server.
#
# Todo:
#   - Encode format for each message and reply with
#     events.codes['needmoreparams']
#   - starting server when already started doesn't work properly. PID
#     file is not changed, no error messsage is displayed.
#   - Delete channel if last user leaves.
#   - [ERROR] <socket.error instance at 0x7f9f203dfb90>
#     (better error msg required)
#   - Empty channels are left behind
#   - No Op assigned when new channel is created.
#   - User can /join multiple times (doesn't add more to channel,
#     does say 'joined')
#   - PING timeouts
#   - Allow all numerical commands.
#   - Users can send commands to channels they are not in (PART)
# Not Todo (Won't be supported)
#   - Server linking.

import argparse
import errno
import logging
import re
import select
import socketserver
import typing

import jaraco.logging
from jaraco.stream import buffer

import irc.client

from . import events

log = logging.getLogger(__name__)


class IRCError(Exception):
    """
    Exception thrown by IRC command handlers to notify client of a
    server/client error.
    """

    def __init__(self, code, value):
        self.code = code
        self.value = value

    def __str__(self):
        return repr(self.value)

    @classmethod
    def from_name(cls, name, value):
        return cls(events.codes[name], value)


class IRCChannel:
    """
    An IRC channel.
    """

    def __init__(self, name, topic='No topic'):
        self.name = name
        self.topic_by = 'Unknown'
        self.topic = topic
        self.clients = set()


class IRCClient(socketserver.BaseRequestHandler):
    """
    IRC client connect and command handling. Client connection is handled by
    the ``handle`` method which sets up a two-way communication
    with the client.
    It then handles commands sent by the client by dispatching them to the
    ``handle_`` methods.
    """

    class Disconnect(BaseException):
        pass

    def __init__(self, request, client_address, server):
        self.user = None
        self.host = client_address  # Client's hostname / ip.
        self.realname = None  # Client's real name
        self.nick = None  # Client's currently registered nickname
        self.send_queue = []  # Messages to send to client (strings)
        self.channels = {}  # Channels the client is in

        super().__init__(request, client_address, server)

    def handle(self):
        log.info('Client connected: %s', self.client_ident())
        self.buffer = buffer.LineBuffer()

        try:
            while True:
                self._handle_one()
        except self.Disconnect:
            self.request.close()

    def _handle_one(self):
        """
        Handle one read/write cycle.
        """
        ready_to_read, ready_to_write, in_error = select.select(
            [self.request], [self.request], [self.request], 0.1
        )

        if in_error:
            raise self.Disconnect()

        # Write any commands to the client
        while self.send_queue and ready_to_write:
            msg = self.send_queue.pop(0)
            self._send(msg)

        # See if the client has any commands for us.
        if ready_to_read:
            self._handle_incoming()

    def _handle_incoming(self):
        try:
            data = self.request.recv(1024)
        except Exception as err:
            raise self.Disconnect() from err

        if not data:
            raise self.Disconnect()

        self.buffer.feed(data)
        for line in self.buffer:
            line = line.decode('utf-8')
            self._handle_line(line)

    def _handle_line(self, line):
        response = None

        try:
            log.debug(f'from {self.client_ident()}: {line}')
            command, sep, params = line.partition(' ')
            handler = getattr(self, f'handle_{command.lower()}', None)
            if not handler:
                log.info(f'No handler for command: {command}. Full line: {line}')
                raise IRCError.from_name(
                    'unknowncommand', f'{command} :Unknown command'
                )
            response = handler(params)
        except AttributeError as e:
            log.error(str(e))
            raise
        except IRCError as e:
            response = f':{self.server.servername} {e.code} {e.value}'
            log.warning(response)
        except Exception as e:
            response = f':{self.server.servername} ERROR {e!r}'
            log.error(response)
            raise

        if response:
            self._send(response)

    def _send(self, msg):
        log.debug('to %s: %s', self.client_ident(), msg)
        try:
            self.request.send(msg.encode('utf-8') + b'\r\n')
        except OSError as e:
            if e.errno == errno.EPIPE:
                raise self.Disconnect() from e
            else:
                raise

    def handle_nick(self, params):
        """
        Handle the initial setting of the user's nickname and nick changes.
        """
        nick = params

        # Valid nickname?
        if re.search(r'[^a-zA-Z0-9\-\[\]\'`^{}_]', nick):
            raise IRCError.from_name('erroneusnickname', f':{nick}')

        if self.server.clients.get(nick, None) == self:
            # Already registered to user
            return

        if nick in self.server.clients:
            # Someone else is using the nick
            raise IRCError.from_name('nicknameinuse', f'NICK :{nick}')

        if not self.nick:
            # New connection and nick is available; register and send welcome
            # and MOTD.
            self.nick = nick
            self.server.clients[nick] = self
            msg = f"Welcome to {__name__} v{irc._get_version()}."
            response = ':{} {} {} :{}'.format(
                self.server.servername,
                events.codes['welcome'],
                self.nick,
                msg,
            )
            self.send_queue.append(response)
            response = (
                f':{self.server.servername} 376 {self.nick} :End of MOTD command.'
            )
            self.send_queue.append(response)
            return

        # Nick is available. Change the nick.
        message = f':{self.client_ident()} NICK :{nick}'

        self.server.clients.pop(self.nick)
        self.nick = nick
        self.server.clients[self.nick] = self

        # Send a notification of the nick change to all the clients in the
        # channels the client is in.
        for channel in self.channels.values():
            self._send_to_others(message, channel)

        # Send a notification of the nick change to the client itself
        return message

    def handle_user(self, params):
        """
        Handle the USER command which identifies the user to the server.
        """
        params = params.split(' ', 3)

        if len(params) != 4:
            raise IRCError.from_name('needmoreparams', 'USER :Not enough parameters')

        user, mode, unused, realname = params
        self.user = user
        self.mode = mode
        self.realname = realname
        return ''

    def handle_ping(self, params):
        """
        Handle client PING requests to keep the connection alive.
        """
        response = ':{self.server.servername} PONG :{self.server.servername}'
        return response.format(**locals())

    def handle_join(self, params):
        """
        Handle the JOINing of a user to a channel. Valid channel names start
        with a # and consist of a-z, A-Z, 0-9 and/or '_'.
        """
        channel_names = params.split(' ', 1)[0]  # Ignore keys
        for channel_name in channel_names.split(','):
            r_channel_name = channel_name.strip()

            # Valid channel name?
            if not re.match('^#([a-zA-Z0-9_])+$', r_channel_name):
                raise IRCError.from_name(
                    'nosuchchannel', f'{r_channel_name} :No such channel'
                )

            # Add user to the channel (create new channel if not exists)
            channel = self.server.channels.setdefault(
                r_channel_name, IRCChannel(r_channel_name)
            )
            channel.clients.add(self)

            # Add channel to user's channel list
            self.channels[channel.name] = channel

            # Send the topic
            response_join = f':{channel.topic_by} TOPIC {channel.name} :{channel.topic}'
            self.send_queue.append(response_join)

            # Send join message to everybody in the channel, including yourself
            # and send user list of the channel back to the user.
            response_join = f':{self.client_ident()} JOIN :{r_channel_name}'
            for client in channel.clients:
                client.send_queue.append(response_join)

            nicks = [client.nick for client in channel.clients]
            response_userlist = f':{self.server.servername} 353 {self.nick} = {channel.name} :{" ".join(nicks)}'
            self.send_queue.append(response_userlist)

            response = f':{self.server.servername} 366 {self.nick} {channel.name} :End of /NAMES list'
            self.send_queue.append(response)

    def handle_privmsg(self, params):
        """
        Handle sending a private message to a user or channel.
        """
        self._send_msg('PRIVMSG', params)

    def handle_notice(self, params):
        """
        Handle sending a notice to a user or channel.
        """
        self._send_msg('NOTICE', params)

    def _send_msg(self, cmd, params):
        """
        A generic message handler (e.g. PRIVMSG and NOTICE)
        """
        target, sep, msg = params.partition(' ')
        if not msg:
            raise IRCError.from_name('needmoreparams', cmd + ' :Not enough parameters')

        message = f':{self.client_ident()} {cmd} {target} {msg}'
        if target.startswith('#') or target.startswith('$'):
            # Message to channel. Check if the channel exists.
            channel = self.server.channels.get(target)
            if not channel:
                raise IRCError.from_name('nosuchnick', cmd + f' :{target}')

            if channel.name not in self.channels:
                # The user isn't in the channel.
                raise IRCError.from_name(
                    'cannotsendtochan', f'{channel.name} :Cannot send to channel'
                )

            self._send_to_others(message, channel)
        else:
            # Message to user
            client = self.server.clients.get(target, None)
            if not client:
                raise IRCError.from_name('nosuchnick', cmd + f' :{target}')

            client.send_queue.append(message)

    def _send_to_others(self, message, channel):
        """
        Send the message to all clients in the specified channel except for
        self.
        """
        other_clients = [client for client in channel.clients if not client == self]
        for client in other_clients:
            client.send_queue.append(message)

    def handle_topic(self, params):
        """
        Handle a topic command.
        """
        channel_name, sep, topic = params.partition(' ')

        channel = self.server.channels.get(channel_name)
        if not channel:
            raise IRCError.from_name('nosuchnick', f'PRIVMSG :{channel_name}')
        if channel.name not in self.channels:
            # The user isn't in the channel.
            raise IRCError.from_name(
                'cannotsendtochan', f'{channel.name} :Cannot send to channel'
            )

        if topic:
            channel.topic = topic.lstrip(':')
            channel.topic_by = self.nick
        message = f':{self.client_ident()} TOPIC {channel_name} :{channel.topic}'
        return message

    def handle_part(self, params):
        """
        Handle a client parting from channel(s).
        """
        for pchannel in params.split(','):
            if pchannel.strip() in self.server.channels:
                # Send message to all clients in all channels user is in, and
                # remove the user from the channels.
                channel = self.server.channels.get(pchannel.strip())
                response = f':{self.client_ident()} PART :{pchannel}'
                if channel:
                    for client in channel.clients:
                        client.send_queue.append(response)
                channel.clients.remove(self)
                self.channels.pop(pchannel)
            else:
                response = f':{self.server.servername} 403 {pchannel} :{pchannel}'
                self.send_queue.append(response)

    def handle_quit(self, params):
        """
        Handle the client breaking off the connection with a QUIT command.
        """
        response = ':{} QUIT :{}'.format(self.client_ident(), params.lstrip(':'))
        # Send quit message to all clients in all channels user is in, and
        # remove the user from the channels.
        for channel in self.channels.values():
            for client in channel.clients:
                client.send_queue.append(response)
            channel.clients.remove(self)

    def handle_dump(self, params):
        """
        Dump internal server information for debugging purposes.
        """
        print("Clients:", self.server.clients)
        for client in self.server.clients.values():
            print(" ", client)
            for channel in client.channels.values():
                print("     ", channel.name)
        print("Channels:", self.server.channels)
        for channel in self.server.channels.values():
            print(" ", channel.name, channel)
            for client in channel.clients:
                print("     ", client.nick, client)

    def handle_ison(self, params):
        response = f':{self.server.servername} 303 {self.client_ident().nick} :'
        if len(params) == 0 or params.isspace():
            response = f':{self.server.servername} 461 {self.client_ident().nick} ISON :Not enough parameters'
            return response
        nickOnline = []
        for nick in params.split(" "):
            if nick in self.server.clients:
                nickOnline.append(nick)
        response += ' '.join(nickOnline)
        return response

    def client_ident(self):
        """
        Return the client identifier as included in many command replies.
        """
        return irc.client.NickMask.from_params(
            self.nick, self.user, self.server.servername
        )

    def finish(self):
        """
        The client conection is finished. Do some cleanup to ensure that the
        client doesn't linger around in any channel or the client list, in case
        the client didn't properly close the connection with PART and QUIT.
        """
        log.info('Client disconnected: %s', self.client_ident())
        response = f':{self.client_ident()} QUIT :EOF from client'
        for channel in self.channels.values():
            if self in channel.clients:
                # Client is gone without properly QUITing or PARTing this
                # channel.
                for client in channel.clients:
                    client.send_queue.append(response)
                channel.clients.remove(self)
        if self.nick:
            self.server.clients.pop(self.nick)
        log.info('Connection finished: %s', self.client_ident())

    def __repr__(self):
        """
        Return a user-readable description of the client
        """
        return f'<{self.__class__.__name__} {self.nick}!{self.user}@{self.host[0]} ({self.realname})>'


class IRCServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

    channels: typing.Dict[str, IRCChannel] = {}
    "Existing channels by channel name"

    clients: typing.Dict[str, IRCClient] = {}
    "Connected clients by nick name"

    def __init__(self, *args, **kwargs):
        self.servername = 'localhost'
        self.channels = {}
        self.clients = {}

        super().__init__(*args, **kwargs)


def get_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-a",
        "--address",
        dest="listen_address",
        default='127.0.0.1',
        help="IP on which to listen",
    )
    parser.add_argument(
        "-p",
        "--port",
        dest="listen_port",
        default=6667,
        type=int,
        help="Port on which to listen",
    )
    jaraco.logging.add_arguments(parser)

    return parser.parse_args()


def main():
    options = get_args()
    jaraco.logging.setup(options)

    log.info("Starting irc.server")

    try:
        bind_address = options.listen_address, options.listen_port
        ircserver = IRCServer(bind_address, IRCClient)
        _tmpl = 'Listening on {listen_address}:{listen_port}'
        log.info(_tmpl.format(**vars(options)))
        ircserver.serve_forever()
    except OSError as e:
        log.error(repr(e))
        raise SystemExit(-2) from None


if __name__ == "__main__":
    main()
