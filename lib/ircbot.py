#! -*- coding: utf-8 -*-

# Copyright (C) 1999-2002  Joel Rosdahl
# Portions Copyring © 2011-2012 Jason R. Coombs
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307  USA
#
# Joel Rosdahl <joel@rosdahl.net>

"""
ircbot -- Simple IRC bot library.

This module contains a single-server IRC bot class that can be used to
write simpler bots.
"""

import sys

import irclib
from irclib import nm_to_n

class SingleServerIRCBot(irclib.SimpleIRCClient):
    """A single-server IRC bot class.

    The bot tries to reconnect if it is disconnected.

    The bot keeps track of the channels it has joined, the other
    clients that are present in the channels and which of those that
    have operator or voice modes.  The "database" is kept in the
    self.channels attribute, which is an IRCDict of Channels.
    """
    def __init__(self, server_list, nickname, realname, reconnection_interval=60):
        """Constructor for SingleServerIRCBot objects.

        Arguments:

            server_list -- A list of tuples (server, port) that
                           defines which servers the bot should try to
                           connect to.

            nickname -- The bot's nickname.

            realname -- The bot's realname.

            reconnection_interval -- How long the bot should wait
                                     before trying to reconnect.

            dcc_connections -- A list of initiated/accepted DCC
            connections.
        """

        super(SingleServerIRCBot, self).__init__()
        self.channels = IRCDict()
        self.server_list = server_list
        if not reconnection_interval or reconnection_interval < 0:
            reconnection_interval = 2 ** 31
        self.reconnection_interval = reconnection_interval

        self._nickname = nickname
        self._realname = realname
        for i in ["disconnect", "join", "kick", "mode",
                  "namreply", "nick", "part", "quit"]:
            self.connection.add_global_handler(i,
                                               getattr(self, "_on_" + i),
                                               -20)

    def _connected_checker(self):
        """[Internal]"""
        if not self.connection.is_connected():
            self.connection.execute_delayed(self.reconnection_interval,
                                            self._connected_checker)
            self.jump_server()

    def _connect(self):
        """[Internal]"""
        password = None
        if len(self.server_list[0]) > 2:
            password = self.server_list[0][2]
        try:
            self.connect(self.server_list[0][0],
                         self.server_list[0][1],
                         self._nickname,
                         password,
                         ircname=self._realname)
        except irclib.ServerConnectionError:
            pass

    def _on_disconnect(self, c, e):
        """[Internal]"""
        self.channels = IRCDict()
        self.connection.execute_delayed(self.reconnection_interval,
                                        self._connected_checker)

    def _on_join(self, c, e):
        """[Internal]"""
        ch = e.target()
        nick = nm_to_n(e.source())
        if nick == c.get_nickname():
            self.channels[ch] = Channel()
        self.channels[ch].add_user(nick)

    def _on_kick(self, c, e):
        """[Internal]"""
        nick = e.arguments()[0]
        channel = e.target()

        if nick == c.get_nickname():
            del self.channels[channel]
        else:
            self.channels[channel].remove_user(nick)

    def _on_mode(self, c, e):
        """[Internal]"""
        modes = irclib.parse_channel_modes(" ".join(e.arguments()))
        t = e.target()
        if irclib.is_channel(t):
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
        """[Internal]"""

        # e.arguments()[0] == "@" for secret channels,
        #                     "*" for private channels,
        #                     "=" for others (public channels)
        # e.arguments()[1] == channel
        # e.arguments()[2] == nick list

        ch = e.arguments()[1]
        for nick in e.arguments()[2].split():
            if nick[0] == "@":
                nick = nick[1:]
                self.channels[ch].set_mode("o", nick)
            elif nick[0] == "+":
                nick = nick[1:]
                self.channels[ch].set_mode("v", nick)
            self.channels[ch].add_user(nick)

    def _on_nick(self, c, e):
        """[Internal]"""
        before = nm_to_n(e.source())
        after = e.target()
        for ch in self.channels.values():
            if ch.has_user(before):
                ch.change_nick(before, after)

    def _on_part(self, c, e):
        """[Internal]"""
        nick = nm_to_n(e.source())
        channel = e.target()

        if nick == c.get_nickname():
            del self.channels[channel]
        else:
            self.channels[channel].remove_user(nick)

    def _on_quit(self, c, e):
        """[Internal]"""
        nick = nm_to_n(e.source())
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
        return "ircbot.py by Joel Rosdahl <joel@rosdahl.net>"

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
        if e.arguments()[0] == "VERSION":
            c.ctcp_reply(nm_to_n(e.source()),
                         "VERSION " + self.get_version())
        elif e.arguments()[0] == "PING":
            if len(e.arguments()) > 1:
                c.ctcp_reply(nm_to_n(e.source()),
                             "PING " + e.arguments()[1])
        elif e.arguments()[0] == "DCC" and e.arguments()[1].split(" ", 1)[0] == "CHAT":
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

    def has_user(self, nick):
        """Check whether the channel has a user."""
        return nick in self.userdict

    def is_oper(self, nick):
        """Check whether a user has operator status in the channel."""
        return nick in self.operdict

    def is_voiced(self, nick):
        """Check whether a user has voice mode set in the channel."""
        return nick in self.voiceddict

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

# from jaraco.util.dictlib
class KeyTransformingDict(dict):
    """
    A dict subclass that transforms the keys before they're used.
    Subclasses may override the default key_transform to customize behavior.
    """
    @staticmethod
    def key_transform(key):
        return key

    def __init__(self, *args, **kargs):
        super(KeyTransformingDict, self).__init__()
        # build a dictionary using the default constructs
        d = dict(*args, **kargs)
        # build this dictionary using transformed keys.
        for item in d.items():
            self.__setitem__(*item)

    def __setitem__(self, key, val):
        key = self.key_transform(key)
        super(KeyTransformingDict, self).__setitem__(key, val)

    def __getitem__(self, key):
        key = self.key_transform(key)
        return super(KeyTransformingDict, self).__getitem__(key)

    def __contains__(self, key):
        key = self.key_transform(key)
        return super(KeyTransformingDict, self).__contains__(key)

    def __delitem__(self, key):
        key = self.key_transform(key)
        return super(KeyTransformingDict, self).__delitem__(key)

    def setdefault(self, key, *args, **kwargs):
        key = self.key_transform(key)
        return super(KeyTransformingDict, self).setdefault(key, *args, **kwargs)

    def pop(self, key, *args, **kwargs):
        key = self.key_transform(key)
        return super(KeyTransformingDict, self).pop(key, *args, **kwargs)

class IRCDict(KeyTransformingDict):
    """
    A dictionary of names whose keys are case-insensitive according to the
    IRC RFC rules.

    >>> d = IRCDict({'[This]': 'that'}, A='foo')

    The dict maintains the original case:
    >>> d.keys()
    ['A', '[This]']

    But the keys can be referenced with a different case
    >>> d['a']
    'foo'

    >>> d['{this}']
    'that'

    >>> d['{THIS}']
    'that'

    >>> '{thiS]' in d
    True

    This should work for operations like delete and pop as well.
    >>> d.pop('A')
    'foo'
    >>> del d['{This}']
    >>> len(d)
    0
    """
    @staticmethod
    def key_transform(key):
        if isinstance(key, basestring):
            key = irclib.IRCFoldedCase(key)
        return key
