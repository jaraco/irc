# THIS IS PROBABLY MOSTLY USELESS, ERRONEOUS, BUGGY AND UNTESTED CODE RIGHT NOW.
#
# Copyright (C) 1999 Joel Rosdahl
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#        
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# Joel Rosdahl <joel@rosdahl.net>
#
# $Id$

import sys

from irclib import *

class SingleServerIRCBot:
    def __init__(self, server_list, nickname, realname, channels_file="bot.channels"):
        self.channels = {}
        self.irc = IRC()
        self.server_list = server_list
        self.current_server = 0
        self.channels_file = channels_file

        try:
            f = open(channels_file, "r")
        except:
            f = open(channels_file, "w")
            f.close()
            f = open(channels_file, "r")
        for ch in f.readlines():
            self.channels[ch[:-1]] = Channel(ch[:-1])
        f.close()

        self.nickname = nickname
        self.realname = realname
        self.connect()
        for numeric in all_events:
            self.connection.add_global_handler(numeric, self.event_dispatcher)

    def connect(self):
        password = None
        if len(self.server_list[self.current_server]) > 2:
            password = self.server_list[self.current_server][2]
        self.connection = self.irc.server_connect(self.server_list[self.current_server][0],
                                                  self.server_list[self.current_server][1],
                                                  self.nickname,
                                                  self.nickname,
                                                  self.realname,
                                                  password)

    def jump_server(self):
        self.get_connection().quit("Jumping servers")
        self.current_server = (self.current_server + 1) % len(self.server_list)
        self.connect()

    def start(self):
        self.irc.process_forever()

    def get_connection(self):
        return self.connection

    def get_irc_object(self):
        return self.ircobj

    def join_new_channel(self, channel):
        self.channels[channel] = Channel(channel)
        self.get_connection().join(channel)
        f = open(self.channels_file, "w")
        f.writelines(map(lambda x: x+"\n", self.channels.keys()))
        f.close()

    def part_old_channel(self, channel):
        self.get_connection().part(channel)
        del self.channels[channel]
        f = open(self.channels_file, "w")
        f.writelines(map(lambda x: x+"\n", self.channels.keys()))
        f.close()

    def die(self):
        self.connection.exit("I'll be back!")

    def get_version(self):
        return "IRCBot by Joel Rosdahl <joel@rosdahl.net>"

    def event_dispatcher(self, c, e):
        try:
            method = getattr(self, "on_" + e.eventtype())
        except AttributeError:
            # No such handler.
            return
        apply(method, (c, e))

    def on_welcome(self, c, e):
        for ch in self.channels.keys():
            c.join(ch)

    def on_ctcp(self, c, e):
        if e.arguments()[0] == "VERSION":
            c.ctcp_reply(nick_from_nickmask(e.source()), self.get_version())
        elif e.arguments()[0] == "PING":
            if len(e.arguments()) > 1:
                c.ctcp_reply(nick_from_nickmask(e.source()), "PING " + e.arguments()[1])
    
    def on_error(self, c, e):
        self.jump_server()
        # XXX join channels here, etc.
        
    def on_join(self, c, e):
        self.channels[lower_irc_string(e.target())].add_nick(e.source())
        if e.source() == c.get_nick_name():
            self.channels[lower_irc_string(e.target())].set_joined()
    
    def on_kick(self, c, e):
        if e.arguments()[0] == self.nickname:
            self.channels[lower_irc_string(e.target())].clear_joined()
            if self.channels[lower_irc_string(e.target())].auto_join():
                def rejoin(c, channel):
                    c.join(channel)
                c.execute_delayed(10, rejoin, (c, e.target()))
        else:
            self.channels[lower_irc_string(e.target())].remove_nick(e.arguments()[0])
    
    def on_inviteonlychan(self, c, e):
        # XXX
        pass

    def on_bannedfromchan(self, c, e):
        # XXX
        pass

    def on_badchannelkey(self, c, e):
        # XXX
        pass

    def on_namreply(self, c, e):
        # e.arguments()[0] = "="     (why?)
        # e.arguments()[1] = channel
        # e.arguments()[2] = nick list

        flags = ""
        channel = lower_irc_string(e.arguments()[1])
        for nick in string.split(e.arguments()[2]):
            self.channels[channel].add_nick(nick)
            if nick[0] == "@":
                self.channels[channel].add_oper(nick[1:])
            elif nick[0] == "+":
                self.channels[channel].remove_oper(nick[1:])

    def on_mode(self, c, e):
        modes = parse_channel_modes(string.join(e.arguments()))
        if is_channel(e.target()):
            channel = lower_irc_string(e.target())
            for mode in modes:
                if mode[0] == "+":
                    self.channels[channel].set_mode(mode[1], mode[2])
                else:
                    self.channels[channel].clear_mode(mode[1])
        else:
            # Mode on self... XXX
            pass

    def on_nick(self, c, e):
        for channel in self.channels.values():
            if e.source() in channel.users():
                channel.change_nick(e.source(), e.target())
        if nick_from_nickmask(e.source()) == self.nickname:
            self.nickname = e.target()
    
    def on_part(self, c, e):
        if nick_from_nickmask(e.source()) != self.nickname:
            self.channels[lower_irc_string(e.target())].remove_nick(e.source())
    
    def on_privmsg(self, c, e):
        pass
    
    def on_pubmsg(self, c, e):
        pass
    
    def on_quit(self, c, e):
        for channel in self.channels.values():
            if e.source() in channel.users():
                channel.remove_nick(e.source())


class Channel:
    def __init__(self, name, auto_join=1):
        self.name = name
        self.nicks = {}
        self.opers = {}
        self.voiced = {}
        self._auto_join = auto_join
        self.modes = {}
        self.joined = 0

    def get_name(self):
        return self.name

    def is_joined(self):
        return self.joined

    def set_joined(self):
        self.joined = 1

    def clear_joined(self):
        self.joined = 0

    def auto_join(self):
        return self._auto_join

    def users(self):
        return self.nicks.keys()

    def has_user(self, nick):
        return self.nicks.has_keys(nick)

    def is_oper(self, nick):
        return self.opers.has_key(nick)

    def is_voiced(self, nick):
        return self.voiced.has_key(nick)

    def add_nick(self, nick):
        self.nicks[nick] = 1

    def remove_nick(self, nick):
        try:
            del self.nicks[nick]
            return 1
        except KeyError:
            return 0
    
    def add_oper(self, nick):
        self.opers[nick] = 1

    def remove_oper(self, nick):
        try:
            del self.opers[nick]
            return 1
        except KeyError:
            return 0
    
    def add_voice(self, nick):
        self.voiced[nick] = 1

    def remove_voice(self, nick):
        try:
            del self.voiced[nick]
            return 1
        except KeyError:
            return 0
    
    def change_nick(self, before, after):
        self.nicks[after] = self.nicks[before]
        del self.nicks[before]

    def set_mode(self, mode, value=None):
        self.modes[mode] = value

    def clear_mode(self, mode, value=None):
        if self.modes.has_key(mode):
            del self.modes[mode]

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

    def has_message_from_outside_protection(self):
        # Eh... What should it be called, really?
        return self.has_mode("n")

    def has_limit(self):
        return self.has_mode("l")

    def limit(self):
        if self.has_limit():
            return self.modes[l]
        else:
            return None

    def has_key(self):
        return self.has_mode("k")

    def key(self):
        if self.has_key():
            return self.modes["k"]
        else:
            return None

    def is_(self):
        return self.has_mode("")

    def is_(self):
        return self.has_mode("")
