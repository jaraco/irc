# irclib -- IRC protocol client library
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

"""irclib -- IRC protocol client library.

This library is intended to encapsulate the IRC protocol at a quite
low level.  Clients are written by registering callbacks (i.e. not by
inheriting a class), to make it able to use different programming
paradigms easily.  (It should be quite easy to write an
object-oriented wrapper for one server connection, for example.)

The class hierarchy is inspired by the Perl IRC module (Net::IRC).

Joel Rosdahl <joel@rosdahl.net>
"""

import bisect
import re
import select
import socket
import string
import sys
import time
import types

VERSION = 0, 2, 1
DEBUG = 0

# TODO
# ----
# DCC
# (maybe) thread safety
# (maybe) color parser convenience functions
# documentation (including all event types)
# (maybe) add awareness of different types of ircds
# send data asynchronously to the server

# NOTES
# -----
# connection.quit() only sends QUIT to the server.
# ERROR from the server triggers the error event and the disconnect event.
# dropping of the connection triggers the disconnect event.

class IRCError(Exception):
    pass

class IRC:
    def __init__(self, fn_to_add_socket=None,
                 fn_to_remove_socket=None,
                 fn_to_add_timeout=None):
        """Creates an IRC object.

        Optional arguments are fn_to_add_socket, fn_to_remove_socket
        and fn_to_add_timeout.  The first two specify functions that
        will be called with a socket object as argument when the IRC
        object wants to be notified (or stop being notified) of data
        coming on a new socket.  When new data arrives, the method
        process_data should be called.  Similarly, fn_to_add_timeout
        is called with a number of seconds (a floating point number)
        as first argument when the IRC object wants to receive a
        notification (by calling the process_timeout method).  So, if
        e.g. the argument is 42.17, the object wants the
        process_timeout method to be called after 42 seconds and 170
        milliseconds.

        The three arguments mainly exist to be able to use an external
        main loop (for example Tkinter's or PyGTK's main app loop)
        instead of calling the process_forever method.

        An alternative is to just call ServerConnection.process_once()
        once in a while.
        """

        if fn_to_add_socket and fn_to_remove_socket:
            self.fn_to_add_socket = fn_to_add_socket
            self.fn_to_remove_socket = fn_to_remove_socket
        else:
            self.fn_to_add_socket = None
            self.fn_to_remove_socket = None

        self.fn_to_add_timeout = fn_to_add_timeout
        self.connections = []
        self.handlers = {}
        self.delayed_commands = [] # list of tuples in the format (time, function, arguments)

        self.add_global_handler("ping", _ping_ponger, -42)

    def server(self):
        """Creates and returns an IRC server object."""

        c = ServerConnection(self)
        self.connections.append(c)
        return c

    def process_data(self, sockets):
        """Called when there is more data to read.

        The argument is a list of socket objects.
        """
        for s in sockets:
           for c in self.connections:
               if s == c._get_socket():
                   c.process_data()

    def process_timeout(self):
        """Called when a timeout notification is due."""
        t = time.time()
        while self.delayed_commands:
            if t >= self.delayed_commands[0][0]:
                apply(self.delayed_commands[0][1], self.delayed_commands[0][2])
                del self.delayed_commands[0]
            else:
                break

    def process_once(self, timeout=0):
        """Process data from connections once.

        Arguments:
            timeout -- How long the select() call should wait if no
                       data is available (default 0).
        """
        sockets = map(lambda x: x._get_socket(), self.connections)
        sockets = filter(lambda x: x != None, sockets)
        (i, o, e) = select.select(sockets, [], [], timeout)
        self.process_data(i)
        self.process_timeout()

    def process_forever(self):
        """This starts an infinite loop, processing data from connections.

        Timeouts will be processed every second.
        """
        while 1:
            self.process_once(1)

    def disconnect_all(self, message=""):
        """Disconnects all connections."""
        for c in self.connections:
            c.quit(message)
            c.disconnect(message)

    def add_global_handler(self, event, handler, priority=0):
        """Adds a global handler function for a type of event.

        The function is called whenever the specified event is
        triggered in any of the connections.

        The handler functions are called in priority order (lowest
        number is highest priority).  If a handler function returns
        "NO MORE", no more handlers will be called.

        Arguments:
            event -- Event type (a string).
            handler -- Callback function.
            priority -- A number (the lower number, the higher priority).
        """

        if not self.handlers.has_key(event):
            self.handlers[event] = []
        bisect.insort(self.handlers[event], ((priority, handler)))

    def remove_global_handler(self, event, handler):
        """Removes a global handler function.

        Returns 1 on success, otherwise 0.

        Arguments:
            event -- Event type (a string).
            handler -- Callback function.
        """
        if not self.handlers.has_key(event):
            return 0
        for h in self.handlers[event]:
            if handler == h[1]:
                self.handlers[event].remove(h)
        return 1

    def execute_at(self, at, function, arguments):
        """Execute a function at a specified time.

        Arguments:
            at -- Execute at this time (standard "time_t" time).
            function -- Function to call.
            arguments -- Arguments to give the function.
        """
        self.execute_delayed(at-time.time(), function, arguments)

    def execute_delayed(self, delay, function, arguments):
        """Execute a function after a specified time.

        Arguments:
            delay -- How many seconds to wait.
            function -- Function to call.
            arguments -- Arguments to give the function.
        """
        bisect.insort(self.delayed_commands, (delay+time.time(), function, arguments))
        if self.fn_to_add_timeout:
            self.fn_to_add_timeout(delay)

    def _handle_event(self, connection, event):
       if self.handlers.has_key(event.eventtype()):
           for handler in self.handlers[event.eventtype()]:
               if handler[1](connection, event) == "NO MORE":
                   return

    def _remove_connection(self, connection):
        self.connections.remove(connection)
        if self.fn_to_remove_socket:
            self.fn_to_remove_socket(connection._get_socket()) 

_rfc_1459_command_regexp = re.compile("^(:(?P<prefix>[^ ]+) +)?(?P<command>[^ ]+)( +(?P<argument>.+))?")

class Connection:
    """Base class for IRC connections.

    Must be overridden.
    """
    def __init__(self, irclibobj):
        self.irclibobj = irclibobj

    def _get_socket():
        raise IRCError, "Not overridden"

    def execute_at(self, at, function, arguments):
        self.irclibobj.execute_at(at, function, arguments)
        
    def execute_delayed(self, delay, function, arguments):
        self.irclibobj.execute_delayed(delay, function, arguments)

class ServerConnectionError(IRCError):
    pass

class ServerConnection(Connection):
    def __init__(self, irclibobj):
        Connection.__init__(self, irclibobj)
        self.connected = 0  # Not connected yet.

    def connect(self, server, port, nickname, username, ircname, password=None):
        """(Re)connect to a server.

        This function can be called to reconnect a closed connection.

        Returns the ServerConnection object.
        """
        if self.connected:
            self.quit("Changing server")

        self.socket = None
        self.previous_buffer = ""
        self.handlers = {}
        self.real_server_name = ""
        self.real_nickname = nickname
        self.server = server
        self.port = port
        self.nickname = nickname
        self.username = username
        self.ircname = ircname
        self.password = password
        self.localhost = socket.gethostname()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect(self.server, self.port)
        except socket.error, x:
            raise ServerConnectionError, "Couldn't connect to socket: %s" % x
        self.connected = 1
        if self.irclibobj.fn_to_add_socket:
            self.irclibobj.fn_to_add_socket(self.socket)

        # Log on...
        if self.password:
            self.pass_(self.password)
        self.nick(self.nickname)
        self.user(self.username, self.localhost, self.server, self.ircname)
        return self

    def close(self):
        """Close the connection.

        This method closes the connection permanently; after it is
        called, the object is unusable.
        """

        self.disconnect("Closing object")
        self.irclibobj._remove_connection(self)
        
    def _get_socket(self):
        return self.socket

    def get_server_name(self):
        """Get the (real) server name.

        This method returns the (real) server name, or, more
        specifically, what the server calls itself.
        """

        if self.real_server_name:
            return self.real_server_name
        else:
            raise ServerConnectionError, "Not connected yet"

    def get_nick_name(self):
        """Get the (real) nick name.

        This method returns the (real) nick name.  The library keeps
        track of nick changes, so it might not be the nick name that
        was passed to the connect() method.
        """

        return self.real_nickname

    def process_data(self):
        """Process incoming data on the connections.

        This method should be called periodically.  If that seems
        boring, look at the process_forever() method.  You may also
        want to look at the process_once() method.
        """

        try:
            new_data = self.socket.recv(2**14)
        except socket.error, x:
            # The server hung up.
            self.disconnect("Connection reset by peer")
            return
        if not new_data:
            # Read nothing: connection must be down.
            self.disconnect("Connection reset by peer")
            return
          
        lines = string.split(self.previous_buffer + new_data, "\r\n")

        # Huh!?  Crrrrazy EFNet doesn't follow the RFC: their ircd
        # seems to use \n as message separator!  :P
        efnet_kluge = string.split(self.previous_buffer + new_data, "\n")
        if len(efnet_kluge) > len(lines):
            lines = efnet_kluge

        # Save the last, unfinished line.
        self.previous_buffer = lines[-1]
        lines = lines[:-1]

        for line in lines:
            prefix = None
            command = None
            arguments = None
            try:
                self._handle_event(Event("allrawmessages",
                                         self.get_server_name(),
                                         None,
                                         [line]))
            except ServerConnectionError:
                pass

            m = _rfc_1459_command_regexp.match(line)
            if m.group("prefix"):
                prefix = m.group("prefix")
                if not self.real_server_name:
                    self.real_server_name = prefix

            if m.group("command"):
                command = string.lower(m.group("command"))

            if m.group("argument"):
                a = string.split(m.group("argument"), " :", 1)
                arguments = string.split(a[0])
                if len(a) == 2:
                    arguments.append(a[1])

            if command == "nick":
                if nick_from_nickmask(prefix) == self.real_nickname:
                    self.real_nickname = arguments[0]

            if command in ["privmsg", "notice"]:
                target, message = arguments[0], arguments[1]
                messages = _ctcp_dequote(message)

                if command == "privmsg":
                    if is_channel(target):
                        command = "pubmsg"
                else:
                    if is_channel(target):
                        command = "pubnotice"
                    else:
                        command = "privnotice"

                for m in messages:
                    if type(m) is types.TupleType:
                        if command in ["privmsg", "pubmsg"]:
                            command = "ctcp"
                        else:
                            command = "ctcpreply"

                        m = list(m)
                        if DEBUG:
                            print "command: %s, source: %s, target: %s, arguments: %s" % (
                                command, prefix, target, m)
                        self._handle_event(Event(command, prefix, target, m))
                    else:
                        if DEBUG:
                            print "command: %s, source: %s, target: %s, arguments: %s" % (
                                command, prefix, target, [m])
                        self._handle_event(Event(command, prefix, target, [m]))
            else:
                target = None
  
                if command == "quit":
                    arguments = [arguments[0]]
                elif command == "ping":
                    target = arguments[0]
                else:
                    target = arguments[0]
                    arguments = arguments[1:]

                if command == "mode":
                    if not is_channel(target):
                        command = "umode"

                # Translate numerics into more readable strings.
                if numeric_events.has_key(command):
                    command = numeric_events[command]
  
                if DEBUG:
                    print "command: %s, source: %s, target: %s, arguments: %s" % (
                        command, prefix, target, arguments)
                self._handle_event(Event(command, prefix, target, arguments))

    def _handle_event(self, event):
        self.irclibobj._handle_event(self, event)
        if self.handlers.has_key(event.eventtype()):
            for fn in self.handlers[event.eventtype()]:
                fn(self, event)

    def is_connected(self):
        """Return connection status (true if connected, otherwise
        false)."""
        return self.connected

    def add_global_handler(self, *args):
        """See documentation for IRC.add_global_handler."""
        apply(self.irclibobj.add_global_handler, args)

    def action(self, target, action):
        self.ctcp("ACTION", target, action)

    def admin(self, server=""):
        self.send_raw(string.strip(string.join(["ADMIN", server])))

    def ctcp(self, ctcptype, target, parameter=""):
        ctcptype = string.upper(ctcptype)
        self.privmsg(target, "\001%s%s\001" % (ctcptype, parameter and (" " + parameter) or ""))

    def ctcp_reply(self, target, parameter):
        self.notice(target, "\001%s\001" % parameter)

    def disconnect(self, message=""):
        """Hang up the connection."""

        if self.connected == 0:
            return

        self.connected = 0
        try:
            self.socket.close()
        except socket.error, x:
            pass
        self.socket = None
        self._handle_event(Event("disconnect", self.server, "", [message]))

    def globops(self, text):
        self.send_raw("GLOBOPS :" + text)

    def info(self, server=""):
        self.send_raw(string.strip(string.join(["INFO", server])))

    def invite(self, nick, channel):
        self.send_raw(string.strip(string.join(["INVITE", nick, channel])))

    def ison(self, nicks):
        """nicks is a list of nicks"""
        self.send_raw("ISON " + string.join(nicks, ","))

    def join(self, channel, key=""):
        self.send_raw("JOIN %s%s" % (channel, (key and (" " + key))))

    def kick(self, channel, nick, comment=""):
        self.send_raw("KICK %s %s%s" % (channel, nick, (comment and (" :" + comment))))

    def links(self, remote_server="", server_mask=""):
        command = "LINKS"
        if remote_server:
            command = command + " " + remote_server
        if server_mask:
            command = command + " " + server_mask
        self.send_raw(command)

    def list(self, channels=None, server=""):
        command = "LIST"
        if channels:
            command = command + " " + string.join(channels, ",")
        if server:
            command = command + " " + server
        self.send_raw(command)

    def lusers(self, server=""):
        self.send_raw("LUSERS" + (server and (" " + server)))

    def mode(self, target, command):
        self.send_raw("MODE %s %s" % (target, command))

    def motd(self, server=""):
        self.send_raw("MOTD" + (server and (" " + server)))

    def names(self, channels=None):
        self.send_raw("NAMES" + (channels and (" " + string.join(channels, ",")) or ""))

    def nick(self, newnick):
        self.send_raw("NICK " + newnick)

    def notice(self, target, text):
        # Should limit len(text) here!
        self.send_raw("NOTICE %s :%s" % (target, text))

    def oper(self, nick, password):
        self.send_raw("OPER %s %s" % (nick, password))

    def part(self, channels):
        if type(channels) == types.StringType:
            self.send_raw("PART " + channels)
        else:
            self.send_raw("PART " + string.join(channels, ","))

    def pass_(self, password):
        self.send_raw("PASS " + password)

    def ping(self, target, target2=""):
       self.send_raw("PING %s%s" % (target, target2 and (" " + target2)))

    def pong(self, target, target2=""):
       self.send_raw("PONG %s%s" % (target, target2 and (" " + target2)))

    def privmsg(self, target, text):
        # Should limit len(text) here!
        self.send_raw("PRIVMSG %s :%s" % (target, text))

    def privmsg_many(self, targets, text):
        # Should limit len(text) here!
        self.send_raw("PRIVMSG %s :%s" % (string.join(targets, ","), text))

    def quit(self, message=""):
        self.send_raw("QUIT" + (message and (" :" + message)))

    def sconnect(self, target, port="", server=""):
        self.send_raw("CONNECT %s%s%s" % (target,
                                          port and (" " + port),
                                          server and (" " + server)))

    def send_raw(self, string):
        """Send raw string to server.

        The string will be padded with appropriate CR LF.
        """
        try:
            self.socket.send(string + "\r\n")
            if DEBUG:
                print "SENT TO SERVER:", string
        except socket.error, x:
            # Aouch!
            self.disconnect("Connection reset by peer.")

    def squit(self, server, comment=""):
        self.send_raw("SQUIT %s%s" % (server, comment and (" :" + comment)))

    def stats(self, statstype, server=""):
        self.send_raw("STATS %s%s" % (statstype, server and (" " + server)))

    def time(self, server=""):
        self.send_raw("TIME" + (server and (" " + server)))

    def topic(self, channel, new_topic=None):
        if new_topic == None:
            self.send_raw("TOPIC " + channel)
        else:
            self.send_raw("TOPIC %s :%s" % (channel, new_topic))

    def trace(self, target=""):
        self.send_raw("TRACE" + (target and (" " + target)))

    def user(self, username, localhost, server, ircname):
        self.send_raw("USER %s * * :%s" % (username, localhost, server, ircname))

    def userhost(self, nicks):
        self.send_raw("USERHOST " + string.join(nicks, ","))

    def users(self, server=""):
        self.send_raw("USERS" + (server and (" " + server)))

    def version(self, server=""):
        self.send_raw("VERSION" + (server and (" " + server)))
        
    def wallops(self, text):
        self.send_raw("WALLOPS :" + text)

    def who(self, target="", op=""):
        self.send_raw("WHO%s%s" % (target and (" " + target), op and (" o")))

    def whois(self, targets):
        self.send_raw("WHOIS " + string.join(targets, ","))

    def whowas(self, nick, max=None, server=""):
        self.send_raw("WHOWAS %s%s%s" % (nick,
                                         max and (" " + max),
                                         server and (" " + server)))

class Event:
    """Event class.

    Arguments:
        eventtype -- A string describing the event.
        source -- The originator of the event (a nick mask or a server). XXX Correct?
        target -- The target of the event (a nick or a channel). XXX Correct?
        arguments -- Any event specific arguments.
    """
    def __init__(self, eventtype, source, target, arguments=None):
        self._eventtype = eventtype
        self._source = source
        self._target = target
        if arguments:
            self._arguments = arguments
        else:
            self._arguments = []

    def eventtype(self):
       return self._eventtype

    def source(self):
       return self._source

    def target(self):
       return self._target

    def arguments(self):
       return self._arguments

_LOW_LEVEL_QUOTE = "\020"
_CTCP_LEVEL_QUOTE = "\134"
_CTCP_DELIMITER = "\001"

_low_level_mapping = {
    "0": "\000",
    "n": "\n",
    "r": "\r",
    _LOW_LEVEL_QUOTE: _LOW_LEVEL_QUOTE
}

_low_level_regexp = re.compile(_LOW_LEVEL_QUOTE + "(.)")

def mask_matches(nick, mask):
    """Check if a nick matches a mask.

    Returns true if the nick matches, otherwise false.
    """
    nick = lower_irc_string(nick)
    mask = lower_irc_string(mask)
    mask = string.replace(mask, "\\", "\\\\")
    for ch in ".$|[](){}?+":
        mask = string.replace(mask, ch, "\\" + ch)
    mask = string.replace(mask, "?", ".")
    mask = string.replace(mask, "*", ".*")
    r = re.compile(mask, re.IGNORECASE)
    return r.match(nick)

def lower_irc_string(s):
    """Returns a lowercased string, where the definition of lowercased
    comes from the IRC specification (RFC 1459).
    """
    s = string.lower(s)
    s = string.replace(s, "[", "{")
    s = string.replace(s, "\\", "|")
    s = string.replace(s, "]", "}")
    s = string.replace(s, "^", "~")
    return s

def _ctcp_dequote(message):
    """Dequote a message according to CTCP specifications.

    The function returns a list where each element can be either a
    string (normal message) or a tuple of one or two strings (tagged
    messages).  If a tuple has only one element (ie is a singleton),
    that element is the tag; otherwise the tuple has two elements: the
    tag and the data.

    Arguments:
        message -- The message to be decoded.
    """

    def _low_level_replace(match_obj):
        ch = match_obj.group(1)

        # If low_level_mapping doesn't have the character as key, we
        # should just return the character.
        return _low_level_mapping.get(ch, ch)

    if _LOW_LEVEL_QUOTE in message:
        # Yup, there was a quote.  Release the dequoter, man!
        message = _low_level_regexp.sub(_low_level_replace, message)

    if _CTCP_DELIMITER not in message:
        return [message]
    else:
        # Split it into parts.  (Does any IRC client actually *use*
        # CTCP stacking like this?)
        chunks = string.split(message, _CTCP_DELIMITER)

        messages = []
        i = 0
        while i < len(chunks)-1:
            # Add message if it's non-empty.
            if len(chunks[i]) > 0:
                messages.append(chunks[i])

            if i < len(chunks)-2:
                # Aye!  CTCP tagged data ahead!
                messages.append(tuple(string.split(chunks[i+1], " ", 1)))

            i = i + 2

        if len(chunks) % 2 == 0:
            # Hey, a lonely _CTCP_DELIMITER at the end!  This means
            # that the last chunk, including the delimiter, is a
            # normal message!  (This is according to the CTCP
            # specification.)
            messages.append(_CTCP_DELIMITER + chunks[-1])
        
        return messages

def is_channel(string):
    """Returns true if the argument is a channel name, otherwise
    false."""
    return string and string[0] in "#&+"

def nick_from_nickmask(s):
    """Returns the nickname part of a nickmask.  (The source of an
    Event is a nickmask.)
    """
    return string.split(s, "!")[0]

def userhost_from_nickmask(s):
    """Returns the userhost part of a nickmask.  (The source of an
    Event is a nickmask.)
    """
    return string.split(s, "!")[1]

def host_from_nickmask(s):
    """Returns the host part of a nickmask.  (The source of an
    Event is a nickmask.)
    """
    return string.split(s, "@")[1]

def user_from_nickmask(s):
    """Returns the user part of a nickmask.  (The source of an
    Event is a nickmask.)
    """
    s = string.split(s, "!")[1]
    return string.split(s, "@")[0]

def parse_nick_modes(mode_string):
    """Parse a nick mode string.

    The function returns a list of lists with three members: sign,
    mode and argument.  The sign is "+" or "-".  The argument is
    always None.

    Example:

    >>> irclib.parse_nick_modes("+ab-c")
    [['+', 'a', None], ['+', 'b', None], ['-', 'c', None]]
    """

    return _parse_modes(mode_string, "")

def parse_channel_modes(mode_string):
    """Parse a channel mode string.

    The function returns a list of lists with three members: sign,
    mode and argument.  The sign is "+" or "-".  The argument is None
    if mode isn't one of "b", "k", "l", "v" or "o".

    Example:

    >>> irclib.parse_channel_modes("+ab-c foo")
    [['+', 'a', None], ['+', 'b', 'foo'], ['-', 'c', None]]
    """

    return _parse_modes(mode_string, "bklvo")

def _parse_modes(mode_string, unary_modes=""):
    modes = []
    arg_count = 0

    # State variable.
    sign = ""

    a = string.split(mode_string)
    if len(a) == 0:
        return []
    else:
        mode_part, args = a[0], a[1:]

    if mode_part[0] not in "+-":
        return []
    for ch in mode_part:
        if ch in "+-":
            sign = ch
        elif ch == " ":
            collecting_arguments = 1
        elif ch in unary_modes:
            modes.append([sign, ch, args[arg_count]])
            arg_count = arg_count + 1
        else:
            modes.append([sign, ch, None])
    return modes

def _ping_ponger(connection, event):
    connection.pong(event.target())

nick_characters = "]ABCDEFGHIJKLMNOPQRSTUVXYZabcdefghijklmnopqrstuvxyz0123456789\\[-`^{}"

# Numeric table mostly stolen from the Perl IRC module (Net::IRC).
numeric_events = {
    "001": "welcome",
    "002": "yourhost",
    "003": "created",
    "004": "myinfo",
    "005": "featurelist",  # XXX
    "200": "tracelink",
    "201": "traceconnecting",
    "202": "tracehandshake",
    "203": "traceunknown",
    "204": "traceoperator",
    "205": "traceuser",
    "206": "traceserver",
    "208": "tracenewtype",
    "209": "traceclass",
    "211": "statslinkinfo",
    "212": "statscommands",
    "213": "statscline",
    "214": "statsnline",
    "215": "statsiline",
    "216": "statskline",
    "217": "statsqline",
    "218": "statsyline",
    "219": "endofstats",
    "221": "umodeis",
    "231": "serviceinfo",
    "232": "endofservices",
    "233": "service",
    "234": "servlist",
    "235": "servlistend",
    "241": "statslline",
    "242": "statsuptime",
    "243": "statsoline",
    "244": "statshline",
    "250": "luserconns",
    "251": "luserclient",
    "252": "luserop",
    "253": "luserunknown",
    "254": "luserchannels",
    "255": "luserme",
    "256": "adminme",
    "257": "adminloc1",
    "258": "adminloc2",
    "259": "adminemail",
    "261": "tracelog",
    "262": "endoftrace",
    "265": "n_local",
    "266": "n_global",
    "300": "none",
    "301": "away",
    "302": "userhost",
    "303": "ison",
    "305": "unaway",
    "306": "nowaway",
    "311": "whoisuser",
    "312": "whoisserver",
    "313": "whoisoperator",
    "314": "whowasuser",
    "315": "endofwho",
    "316": "whoischanop",
    "317": "whoisidle",
    "318": "endofwhois",
    "319": "whoischannels",
    "321": "liststart",
    "322": "list",
    "323": "listend",
    "324": "channelmodeis",
    "329": "channelcreate",
    "331": "notopic",
    "332": "topic",
    "333": "topicinfo",
    "341": "inviting",
    "342": "summoning",
    "351": "version",
    "352": "whoreply",
    "353": "namreply",
    "361": "killdone",
    "362": "closing",
    "363": "closeend",
    "364": "links",
    "365": "endoflinks",
    "366": "endofnames",
    "367": "banlist",
    "368": "endofbanlist",
    "369": "endofwhowas",
    "371": "info",
    "372": "motd",
    "373": "infostart",
    "374": "endofinfo",
    "375": "motdstart",
    "376": "endofmotd",
    "377": "motd2",        # 1997-10-16 -- tkil
    "381": "youreoper",
    "382": "rehashing",
    "384": "myportis",
    "391": "time",
    "392": "usersstart",
    "393": "users",
    "394": "endofusers",
    "395": "nousers",
    "401": "nosuchnick",
    "402": "nosuchserver",
    "403": "nosuchchannel",
    "404": "cannotsendtochan",
    "405": "toomanychannels",
    "406": "wasnosuchnick",
    "407": "toomanytargets",
    "409": "noorigin",
    "411": "norecipient",
    "412": "notexttosend",
    "413": "notoplevel",
    "414": "wildtoplevel",
    "421": "unknowncommand",
    "422": "nomotd",
    "423": "noadmininfo",
    "424": "fileerror",
    "431": "nonicknamegiven",
    "432": "erroneusnickname", # Thiss iz how its speld in thee RFC.
    "433": "nicknameinuse",
    "436": "nickcollision",
    "441": "usernotinchannel",
    "442": "notonchannel",
    "443": "useronchannel",
    "444": "nologin",
    "445": "summondisabled",
    "446": "usersdisabled",
    "451": "notregistered",
    "461": "needmoreparams",
    "462": "alreadyregistered",
    "463": "nopermforhost",
    "464": "passwdmismatch",
    "465": "yourebannedcreep", # I love this one...
    "466": "youwillbebanned",
    "467": "keyset",
    "471": "channelisfull",
    "472": "unknownmode",
    "473": "inviteonlychan",
    "474": "bannedfromchan",
    "475": "badchannelkey",
    "476": "badchanmask",
    "481": "noprivileges",
    "482": "chanoprivsneeded",
    "483": "cantkillserver",
    "491": "nooperhost",
    "492": "noservicehost",
    "501": "umodeunknownflag",
    "502": "usersdontmatch",
}

generated_events = [
    # Generated events
    "disconnect",
    "ctcp",
    "ctcpreply"
]

protocol_events = [
    # IRC protocol events
    "error",
    "join",
    "kick",
    "mode",
    "part",
    "ping",
    "privmsg",
    "privnotice",
    "pubmsg",
    "pubnotice",
    "quit"
]

all_events = generated_events + protocol_events + numeric_events.values()
