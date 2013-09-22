# -*- coding: utf-8 -*-

# Copyright (C) 1999-2002  Joel Rosdahl
# Portions Copyright © 2011-2012 Jason R. Coombs

"""
Simple IRC bot library.

This module contains a single-server IRC bot class that can be used to
write simpler bots.
"""

from __future__ import absolute_import

import sys

import irc.client
import irc.modes
from .dict import IRCDict

class ServerSpec(object):
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

class SingleServerIRCBot(irc.client.SimpleIRCClient):
    """A single-server IRC bot class.

    The bot tries to reconnect if it is disconnected.

    The bot keeps track of the channels it has joined, the other
    clients that are present in the channels and which of those that
    have operator or voice modes.  The "database" is kept in the
    self.channels attribute, which is an IRCDict of Channels.
    """
    def __init__(self, server_list, nickname, realname,
            reconnection_interval=60, **connect_params):
        """Constructor for SingleServerIRCBot objects.

        Arguments:

            server_list -- A list of ServerSpec objects or tuples of
                           parameters suitable for constructing ServerSpec
                           objects. Defines the list of servers the bot will
                           use (in order).

            nickname -- The bot's nickname.

            realname -- The bot's realname.

            reconnection_interval -- How long the bot should wait
                                     before trying to reconnect.

            dcc_connections -- A list of initiated/accepted DCC
            connections.

            **connect_params -- parameters to pass through to the connect
                                method.
        """

        super(SingleServerIRCBot, self).__init__()
        self.__connect_params = connect_params
        self.channels = IRCDict()
        self.server_list = [
            ServerSpec(*server)
                if isinstance(server, (tuple, list))
                else server
            for server in server_list
        ]
        assert all(
            isinstance(server, ServerSpec)
            for server in self.server_list
        )
        if not reconnection_interval or reconnection_interval < 0:
            reconnection_interval = 2 ** 31
        self.reconnection_interval = reconnection_interval

        self._nickname = nickname
        self._realname = realname
        for i in ["disconnect", "join", "kick", "mode",
                  "namreply", "nick", "part", "quit"]:
            self.connection.add_global_handler(i, getattr(self, "_on_" + i),
                -20)

    def _connected_checker(self):
        """[Internal]"""
        if not self.connection.is_connected():
            self.connection.execute_delayed(self.reconnection_interval,
                                            self._connected_checker)
            self.jump_server()

    def _connect(self):
        """
        Establish a connection to the server at the front of the server_list.
        """
        server = self.server_list[0]
        try:
            self.connect(server.host, server.port, self._nickname,
                server.password, ircname=self._realname,
                **self.__connect_params)
        except irc.client.ServerConnectionError:
            pass

    def _on_disconnect(self, c, e):
        self.channels = IRCDict()
        self.connection.execute_delayed(self.reconnection_interval,
                                        self._connected_checker)

    def _on_join(self, c, e):
        ch = e.target
        nick = e.source.nick
        if nick == c.get_nickname():
            self.channels[ch] = Channel()
        self.channels[ch].add_user(nick)

    def _on_kick(self, c, e):
        nick = e.arguments[0]
        channel = e.target

        if nick == c.get_nickname():
            del self.channels[channel]
        else:
            self.channels[channel].remove_user(nick)

    def _on_mode(self, c, e):
        modes = irc.modes.parse_channel_modes(" ".join(e.arguments))
        t = e.target
        if irc.client.is_channel(t):
            ch = self.channels[t]
            for mode in modes:
                if mode[0] == "+":
                    f = ch.set_mode
                else:
                    f = ch.clear_mode
                f(mode[1], mode[2])
        else:
            # Mode on self... XXX
            pass

    def _on_namreply(self, c, e):
        # e.arguments[0] == "@" for secret channels,
        #                     "*" for private channels,
        #                     "=" for others (public channels)
        # e.arguments[1] == channel
        # e.arguments[2] == nick list

        ch_type, channel, nick_list = e.arguments

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

    def _on_nick(self, c, e):
        before = e.source.nick
        after = e.target
        for ch in self.channels.values():
            if ch.has_user(before):
                ch.change_nick(before, after)

    def _on_part(self, c, e):
        nick = e.source.nick
        channel = e.target

        if nick == c.get_nickname():
            del self.channels[channel]
        else:
            self.channels[channel].remove_user(nick)

    def _on_quit(self, c, e):
        nick = e.source.nick
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
        return "Python irc.bot ({version})".format(
            version=irc.client.VERSION_STRING)

    def jump_server(self, msg="Changing servers"):
        """Connect to a new server, possibly disconnecting from the current.

        The bot will skip to next server in the server_list each time
        jump_server is called.
        """
        if self.connection.is_connected():
            self.connection.disconnect(msg)

        self.server_list.append(self.server_list.pop(0))
        self._connect()

    def on_ctcp(self, c, e):
        """Default handler for ctcp events.

        Replies to VERSION and PING requests and relays DCC requests
        to the on_dccchat method.
        """
        nick = e.source.nick
        if e.arguments[0] == "VERSION":
            c.ctcp_reply(nick, "VERSION " + self.get_version())
        elif e.arguments[0] == "PING":
            if len(e.arguments) > 1:
                c.ctcp_reply(nick, "PING " + e.arguments[1])
        elif e.arguments[0] == "DCC" and e.arguments[1].split(" ", 1)[0] == "CHAT":
            self.on_dccchat(c, e)

    def on_dccchat(self, c, e):
        pass

    def start(self):
        """Start the bot."""
        self._connect()
        super(SingleServerIRCBot, self).start()


class Channel(object):
    """A class for keeping information about an IRC channel.

    This class can be improved a lot.
    """

    def __init__(self):
        self.userdict = IRCDict()
        self.operdict = IRCDict()
        self.voiceddict = IRCDict()
        self.ownerdict = IRCDict()
        self.halfopdict = IRCDict()
        self.modes = {}

    def users(self):
        """Returns an unsorted list of the channel's users."""
        return self.userdict.keys()

    def opers(self):
        """Returns an unsorted list of the channel's operators."""
        return self.operdict.keys()

    def voiced(self):
        """Returns an unsorted list of the persons that have voice
        mode set in the channel."""
        return self.voiceddict.keys()

    def owners(self):
        """Returns an unsorted list of the channel's owners."""
        return self.ownerdict.keys()

    def halfops(self):
        """Returns an unsorted list of the channel's half-operators."""
        return self.halfopdict.keys()

    def has_user(self, nick):
        """Check whether the channel has a user."""
        return nick in self.userdict

    def is_oper(self, nick):
        """Check whether a user has operator status in the channel."""
        return nick in self.operdict

    def is_voiced(self, nick):
        """Check whether a user has voice mode set in the channel."""
        return nick in self.voiceddict

    def is_owner(self, nick):
        """Check whether a user has owner status in the channel."""
        return nick in self.ownerdict

    def is_halfop(self, nick):
        """Check whether a user has half-operator status in the channel."""
        return nick in self.halfopdict

    def add_user(self, nick):
        self.userdict[nick] = 1

    def remove_user(self, nick):
        for d in self.userdict, self.operdict, self.voiceddict:
            if nick in d:
                del d[nick]

    def change_nick(self, before, after):
        self.userdict[after] = self.userdict.pop(before)
        if before in self.operdict:
            self.operdict[after] = self.operdict.pop(before)
        if before in self.voiceddict:
            self.voiceddict[after] = self.voiceddict.pop(before)

    def set_userdetails(self, nick, details):
        if nick in self.userdict:
            self.userdict[nick] = details

    def set_mode(self, mode, value=None):
        """Set mode on the channel.

        Arguments:

            mode -- The mode (a single-character string).

            value -- Value
        """
        if mode == "o":
            self.operdict[value] = 1
        elif mode == "v":
            self.voiceddict[value] = 1
        elif mode == "q":
            self.ownerdict[value] = 1
        elif mode == "h":
            self.halfopdict[value] = 1
        else:
            self.modes[mode] = value

    def clear_mode(self, mode, value=None):
        """Clear mode on the channel.

        Arguments:

            mode -- The mode (a single-character string).

            value -- Value
        """
        try:
            if mode == "o":
                del self.operdict[value]
            elif mode == "v":
                del self.voiceddict[value]
            elif mode == "q":
                del self.ownerdict[value]
            elif mode == "h":
                del self.halfopdict[value]
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
