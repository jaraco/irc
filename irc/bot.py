# -*- coding: utf-8 -*-

"""
Simple IRC bot library.

This module contains a single-server IRC bot class that can be used to
write simpler bots.
"""

import sys
import collections
import warnings
import abc
import itertools
import random

import more_itertools

import irc.client
import irc.modes
from .dict import IRCDict


class ServerSpec:
    """
    An IRC server specification.

    >>> spec = ServerSpec('localhost')
    >>> spec.host
    'localhost'
    >>> spec.port
    6667
    >>> spec.password

    >>> spec = ServerSpec('127.0.0.1', 6697, 'fooP455')
    >>> spec.password
    'fooP455'
    """

    def __init__(self, host, port=6667, password=None):
        self.host = host
        self.port = port
        self.password = password

    def __repr__(self):
        return "<irc.bot.ServerSpec for server %s:%s %s>" % (
            self.host,
            self.port,
            "with password" if self.password else "without password",
        )

    @classmethod
    def ensure(cls, input):
        spec = cls(*input) if isinstance(input, (list, tuple)) else input
        assert isinstance(spec, cls)
        return spec


class ReconnectStrategy(metaclass=abc.ABCMeta):
    """
    An abstract base class describing the interface used by
    SingleServerIRCBot for handling reconnect following
    disconnect events.
    """

    @abc.abstractmethod
    def run(self, bot):
        """
        Invoked by the bot on disconnect. Here
        a strategy can determine how to react to a
        disconnect.
        """


class ExponentialBackoff(ReconnectStrategy):
    """
    A ReconnectStrategy implementing exponential backoff
    with jitter.
    """

    min_interval = 60
    max_interval = 300

    def __init__(self, **attrs):
        vars(self).update(attrs)
        assert 0 <= self.min_interval <= self.max_interval
        self._check_scheduled = False
        self.attempt_count = itertools.count(1)

    def run(self, bot):
        self.bot = bot

        if self._check_scheduled:
            return

        # calculate interval in seconds based on connection attempts
        intvl = 2 ** next(self.attempt_count) - 1

        # limit the max interval
        intvl = min(intvl, self.max_interval)

        # add jitter and truncate to integer seconds
        intvl = int(intvl * random.random())

        # limit the min interval
        intvl = max(intvl, self.min_interval)

        self.bot.reactor.scheduler.execute_after(intvl, self.check)
        self._check_scheduled = True

    def check(self):
        self._check_scheduled = False
        if not self.bot.connection.is_connected():
            self.run(self.bot)
            self.bot.jump_server()


missing = object()


class SingleServerIRCBot(irc.client.SimpleIRCClient):
    r"""A single-server IRC bot class.

    The bot tries to reconnect if it is disconnected.

    The bot keeps track of the channels it has joined, the other
    clients that are present in the channels and which of those that
    have operator or voice modes.  The "database" is kept in the
    self.channels attribute, which is an IRCDict of Channels.

    Arguments:

        server_list -- A list of ServerSpec objects or tuples of
            parameters suitable for constructing ServerSpec
            objects. Defines the list of servers the bot will
            use (in order).

        nickname -- The bot's nickname.

        realname -- The bot's realname.

        recon -- A ReconnectStrategy for reconnecting on
            disconnect or failed connection.

        dcc_connections -- A list of initiated/accepted DCC
            connections.

        \*\*connect_params -- parameters to pass through to the connect
            method.
    """

    def __init__(
        self,
        server_list,
        nickname,
        realname,
        reconnection_interval=missing,
        recon=ExponentialBackoff(),
        **connect_params
    ):
        super(SingleServerIRCBot, self).__init__()
        self.__connect_params = connect_params
        self.channels = IRCDict()
        specs = map(ServerSpec.ensure, server_list)
        self.servers = more_itertools.peekable(itertools.cycle(specs))
        self.recon = recon
        # for compatibility
        if reconnection_interval is not missing:
            warnings.warn(
                "reconnection_interval is deprecated; "
                "pass a ReconnectStrategy object instead"
            )
            self.recon = ExponentialBackoff(min_interval=reconnection_interval)

        self._nickname = nickname
        self._realname = realname
        for i in [
            "disconnect",
            "join",
            "kick",
            "mode",
            "namreply",
            "nick",
            "part",
            "quit",
        ]:
            self.connection.add_global_handler(i, getattr(self, "_on_" + i), -20)

    def _connect(self):
        """
        Establish a connection to the server at the front of the server_list.
        """
        server = self.servers.peek()
        try:
            self.connect(
                server.host,
                server.port,
                self._nickname,
                server.password,
                ircname=self._realname,
                **self.__connect_params
            )
        except irc.client.ServerConnectionError:
            pass

    def _on_disconnect(self, connection, event):
        self.channels = IRCDict()
        self.recon.run(self)

    def _on_join(self, connection, event):
        ch = event.target
        nick = event.source.nick
        if nick == connection.get_nickname():
            self.channels[ch] = Channel()
        self.channels[ch].add_user(nick)

    def _on_kick(self, connection, event):
        nick = event.arguments[0]
        channel = event.target

        if nick == connection.get_nickname():
            del self.channels[channel]
        else:
            self.channels[channel].remove_user(nick)

    def _on_mode(self, connection, event):
        t = event.target
        if not irc.client.is_channel(t):
            # mode on self; disregard
            return
        ch = self.channels[t]

        modes = irc.modes.parse_channel_modes(" ".join(event.arguments))
        for sign, mode, argument in modes:
            f = {"+": ch.set_mode, "-": ch.clear_mode}[sign]
            f(mode, argument)

    def _on_namreply(self, connection, event):
        """
        event.arguments[0] == "@" for secret channels,
                          "*" for private channels,
                          "=" for others (public channels)
        event.arguments[1] == channel
        event.arguments[2] == nick list
        """

        ch_type, channel, nick_list = event.arguments

        if channel == '*':
            # User is not in any visible channel
            # http://tools.ietf.org/html/rfc2812#section-3.2.5
            return

        for nick in nick_list.split():
            nick_modes = []

            if nick[0] in self.connection.features.prefix:
                nick_modes.append(self.connection.features.prefix[nick[0]])
                nick = nick[1:]

            for mode in nick_modes:
                self.channels[channel].set_mode(mode, nick)

            self.channels[channel].add_user(nick)

    def _on_nick(self, connection, event):
        before = event.source.nick
        after = event.target
        for ch in self.channels.values():
            if ch.has_user(before):
                ch.change_nick(before, after)

    def _on_part(self, connection, event):
        nick = event.source.nick
        channel = event.target

        if nick == connection.get_nickname():
            del self.channels[channel]
        else:
            self.channels[channel].remove_user(nick)

    def _on_quit(self, connection, event):
        nick = event.source.nick
        for ch in self.channels.values():
            if ch.has_user(nick):
                ch.remove_user(nick)

    def die(self, msg="Bye, cruel world!"):
        """Let the bot die.

        Arguments:

            msg -- Quit message.
        """

        self.connection.disconnect(msg)
        sys.exit(0)

    def disconnect(self, msg="I'll be back!"):
        """Disconnect the bot.

        The bot will try to reconnect after a while.

        Arguments:

            msg -- Quit message.
        """
        self.connection.disconnect(msg)

    def get_version(self):
        """Returns the bot version.

        Used when answering a CTCP VERSION request.
        """
        return "Python irc.bot ({version})".format(version=irc.client.VERSION_STRING)

    def jump_server(self, msg="Changing servers"):
        """Connect to a new server, possibly disconnecting from the current.

        The bot will skip to next server in the server_list each time
        jump_server is called.
        """
        if self.connection.is_connected():
            self.connection.disconnect(msg)

        next(self.servers)
        self._connect()

    def on_ctcp(self, connection, event):
        """Default handler for ctcp events.

        Replies to VERSION and PING requests and relays DCC requests
        to the on_dccchat method.
        """
        nick = event.source.nick
        if event.arguments[0] == "VERSION":
            connection.ctcp_reply(nick, "VERSION " + self.get_version())
        elif event.arguments[0] == "PING":
            if len(event.arguments) > 1:
                connection.ctcp_reply(nick, "PING " + event.arguments[1])
        elif (
            event.arguments[0] == "DCC"
            and event.arguments[1].split(" ", 1)[0] == "CHAT"
        ):
            self.on_dccchat(connection, event)

    def on_dccchat(self, connection, event):
        pass

    def start(self):
        """Start the bot."""
        self._connect()
        super(SingleServerIRCBot, self).start()


class Channel:
    """
    A class for keeping information about an IRC channel.
    """

    user_modes = 'ovqha'
    """
    Modes which are applicable to individual users, and which
    should be tracked in the mode_users dictionary.
    """

    def __init__(self):
        self._users = IRCDict()
        self.mode_users = collections.defaultdict(IRCDict)
        self.modes = {}

    def users(self):
        """Returns an unsorted list of the channel's users."""
        return self._users.keys()

    def opers(self):
        """Returns an unsorted list of the channel's operators."""
        return self.mode_users['o'].keys()

    def voiced(self):
        """Returns an unsorted list of the persons that have voice
        mode set in the channel."""
        return self.mode_users['v'].keys()

    def owners(self):
        """Returns an unsorted list of the channel's owners."""
        return self.mode_users['q'].keys()

    def halfops(self):
        """Returns an unsorted list of the channel's half-operators."""
        return self.mode_users['h'].keys()

    def admins(self):
        """Returns an unsorted list of the channel's admins."""
        return self.mode_users['a'].keys()

    def has_user(self, nick):
        """Check whether the channel has a user."""
        return nick in self._users

    def is_oper(self, nick):
        """Check whether a user has operator status in the channel."""
        return nick in self.mode_users['o']

    def is_voiced(self, nick):
        """Check whether a user has voice mode set in the channel."""
        return nick in self.mode_users['v']

    def is_owner(self, nick):
        """Check whether a user has owner status in the channel."""
        return nick in self.mode_users['q']

    def is_halfop(self, nick):
        """Check whether a user has half-operator status in the channel."""
        return nick in self.mode_users['h']

    def is_admin(self, nick):
        """Check whether a user has admin status in the channel."""
        return nick in self.mode_users['a']

    def add_user(self, nick):
        self._users[nick] = 1

    @property
    def user_dicts(self):
        yield self._users
        for d in self.mode_users.values():
            yield d

    def remove_user(self, nick):
        for d in self.user_dicts:
            d.pop(nick, None)

    def change_nick(self, before, after):
        self._users[after] = self._users.pop(before)
        for mode_lookup in self.mode_users.values():
            if before in mode_lookup:
                mode_lookup[after] = mode_lookup.pop(before)

    def set_userdetails(self, nick, details):
        if nick in self._users:
            self._users[nick] = details

    def set_mode(self, mode, value=None):
        """Set mode on the channel.

        Arguments:

            mode -- The mode (a single-character string).

            value -- Value
        """
        if mode in self.user_modes:
            self.mode_users[mode][value] = 1
        else:
            self.modes[mode] = value

    def clear_mode(self, mode, value=None):
        """Clear mode on the channel.

        Arguments:

            mode -- The mode (a single-character string).

            value -- Value
        """
        try:
            if mode in self.user_modes:
                del self.mode_users[mode][value]
            else:
                del self.modes[mode]
        except KeyError:
            pass

    def has_mode(self, mode):
        return mode in self.modes

    def is_moderated(self):
        return self.has_mode("m")

    def is_secret(self):
        return self.has_mode("s")

    def is_protected(self):
        return self.has_mode("p")

    def has_topic_lock(self):
        return self.has_mode("t")

    def is_invite_only(self):
        return self.has_mode("i")

    def has_allow_external_messages(self):
        return self.has_mode("n")

    def has_limit(self):
        return self.has_mode("l")

    def limit(self):
        if self.has_limit():
            return self.modes["l"]
        else:
            return None

    def has_key(self):
        return self.has_mode("k")
