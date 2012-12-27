"""
irc/server.py

Copyright by Ferry Boender, 2009

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
#   - Encode format for each message and reply with ERR_NEEDMOREPARAMS
#   - starting server when already started doesn't work properly. PID file is not changed, no error messsage is displayed.
#   - Delete channel if last user leaves.
#   - [ERROR] <socket.error instance at 0x7f9f203dfb90> (better error msg required)
#   - Empty channels are left behind
#   - No Op assigned when new channel is created.
#   - User can /join multiple times (doesn't add more to channel, does say 'joined')
#   - Error
#     [<socket._socketobject object at 0x26151a0>] [] []
#     ----------------------------------------
#     Exception happened during processing of request from ('127.0.0.1', 47830)
#     Traceback (most recent call last):
#       File "/usr/lib/python2.6/SocketServer.py", line 560, in process_request_thread
#         self.finish_request(request, client_address)
#       File "/usr/lib/python2.6/SocketServer.py", line 322, in finish_request
#         self.RequestHandlerClass(request, client_address, self)
#       File "./hircd.py", line 102, in __init__
#
#       File "/usr/lib/python2.6/SocketServer.py", line 617, in __init__
#         self.handle()
#       File "./hircd.py", line 120, in handle
#         if len(ready_to_read) == 1 and ready_to_read[0] == self.request:
#     error: [Errno 104] Connection reset by peer
#     ----------------------------------------
#   - PING timeouts
#   - Allow all numerical commands.
#   - Users can send commands to channels they are not in (PART)
# Not Todo (Won't be supported)
#   - Server linking.

#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#

from __future__ import print_function

import sys
import optparse
import logging
import ConfigParser
import os
import SocketServer
import socket
import select
import re

SRV_NAME    = "Hircd"
SRV_VERSION = "0.1"
SRV_WELCOME = "Welcome to %s v%s, the ugliest IRC server in the world." % (SRV_NAME, SRV_VERSION)

RPL_WELCOME          = '001'
ERR_NOSUCHNICK       = '401'
ERR_NOSUCHCHANNEL    = '403'
ERR_CANNOTSENDTOCHAN = '404'
ERR_UNKNOWNCOMMAND   = '421'
ERR_ERRONEUSNICKNAME = '432'
ERR_NICKNAMEINUSE    = '433'
ERR_NEEDMOREPARAMS   = '461'

class IRCError(Exception):
    """
    Exception thrown by IRC command handlers to notify client of a server/client error.
    """
    def __init__(self, code, value):
        self.code = code
        self.value = value

    def __str__(self):
        return repr(self.value)

class IRCChannel(object):
    """
    Object representing an IRC channel.
    """
    def __init__(self, name, topic='No topic'):
        self.name = name
        self.topic_by = 'Unknown'
        self.topic = topic
        self.clients = set()

class IRCClient(SocketServer.BaseRequestHandler):
    """
    IRC client connect and command handling. Client connection is handled by
    the `handle` method which sets up a two-way communication with the client.
    It then handles commands sent by the client by dispatching them to the
    handle_ methods.
    """
    def __init__(self, request, client_address, server):
        self.user = None
        self.host = client_address  # Client's hostname / ip.
        self.realname = None        # Client's real name
        self.nick = None            # Client's currently registered nickname
        self.send_queue = []        # Messages to send to client (strings)
        self.channels = {}          # Channels the client is in

        SocketServer.BaseRequestHandler.__init__(self, request, client_address, server)

    def handle(self):
        logging.info('Client connected: %s' % (self.client_ident(), ))

        while True:
            buf = ''
            ready_to_read, ready_to_write, in_error = select.select([self.request], [], [], 0.1)

            # Write any commands to the client
            while self.send_queue:
                msg = self.send_queue.pop(0)
                logging.debug('to %s: %s' % (self.client_ident(), msg))
                self.request.send(msg + '\n')

            # See if the client has any commands for us.
            if len(ready_to_read) == 1 and ready_to_read[0] == self.request:
                data = self.request.recv(1024)

                if not data:
                    break
                elif len(data) > 0:
                    # There is data. Process it and turn it into line-oriented input.
                    buf += str(data)

                    while buf.find("\n") != -1:
                        line, buf = buf.split("\n", 1)
                        line = line.rstrip()

                        response = ''
                        try:
                            logging.debug('from %s: %s' % (self.client_ident(), line))
                            if ' ' in line:
                                command, params = line.split(' ', 1)
                            else:
                                command = line
                                params = ''
                            handler = getattr(self, 'handle_%s' % (command.lower()), None)
                            if not handler:
                                logging.info('No handler for command: %s. Full line: %s' % (command, line))
                                raise IRCError(ERR_UNKNOWNCOMMAND, '%s :Unknown command' % (command))
                            response = handler(params)
                        except AttributeError, e:
                            raise e
                            logging.error('%s' % (e))
                        except IRCError, e:
                            response = ':%s %s %s' % (self.server.servername, e.code, e.value)
                            logging.error('%s' % (response))
                        except Exception, e:
                            response = ':%s ERROR %s' % (self.server.servername, repr(e))
                            logging.error('%s' % (response))
                            raise

                        if response:
                            logging.debug('to %s: %s' % (self.client_ident(), response))
                            self.request.send(response + '\r\n')

        self.request.close()

    def handle_nick(self, params):
        """
        Handle the initial setting of the user's nickname and nick changes.
        """
        nick = params

        # Valid nickname?
        if re.search('[^a-zA-Z0-9\-\[\]\'`^{}_]', nick):
            raise IRCError(ERR_ERRONEUSNICKNAME, ':%s' % (nick))

        if not self.nick:
            # New connection
            if nick in self.server.clients:
                # Someone else is using the nick
                raise IRCError(ERR_NICKNAMEINUSE, 'NICK :%s' % (nick))
            else:
                # Nick is available, register, send welcome and MOTD.
                self.nick = nick
                self.server.clients[nick] = self
                response = ':%s %s %s :%s' % (self.server.servername, RPL_WELCOME, self.nick, SRV_WELCOME)
                self.send_queue.append(response)
                response = ':%s 376 %s :End of MOTD command.' % (self.server.servername, self.nick)
                self.send_queue.append(response)
                return()
        else:
            if self.server.clients.get(nick, None) == self:
                # Already registered to user
                return
            elif nick in self.server.clients:
                # Someone else is using the nick
                raise IRCError(ERR_NICKNAMEINUSE, 'NICK :%s' % (nick))
            else:
                # Nick is available. Change the nick.
                message = ':%s NICK :%s' % (self.client_ident(), nick)

                self.server.clients.pop(self.nick)
                prev_nick = self.nick
                self.nick = nick
                self.server.clients[self.nick] = self

                # Send a notification of the nick change to all the clients in
                # the channels the client is in.
                for channel in self.channels.values():
                    for client in channel.clients:
                        if client != self: # do not send to client itself.
                            client.send_queue.append(message)

                # Send a notification of the nick change to the client itself
                return(message)

    def handle_user(self, params):
        """
        Handle the USER command which identifies the user to the server.
        """
        if params.count(' ') < 3:
            raise IRCError(ERR_NEEDMOREPARAMS, '%s :Not enough parameters' % (USER))

        user, mode, unused, realname = params.split(' ', 3)
        self.user = user
        self.mode = mode
        self.realname = realname
        return('')

    def handle_ping(self, params):
        """
        Handle client PING requests to keep the connection alive.
        """
        response = ':%s PONG :%s' % (self.server.servername, self.server.servername)
        return (response)

    def handle_join(self, params):
        """
        Handle the JOINing of a user to a channel. Valid channel names start
        with a # and consist of a-z, A-Z, 0-9 and/or '_'.
        """
        channel_names = params.split(' ', 1)[0] # Ignore keys
        for channel_name in channel_names.split(','):
            r_channel_name = channel_name.strip()

            # Valid channel name?
            if not re.match('^#([a-zA-Z0-9_])+$', r_channel_name):
                raise IRCError(ERR_NOSUCHCHANNEL, '%s :No such channel' % (r_channel_name))

            # Add user to the channel (create new channel if not exists)
            channel = self.server.channels.setdefault(r_channel_name, IRCChannel(r_channel_name))
            channel.clients.add(self)

            # Add channel to user's channel list
            self.channels[channel.name] = channel

            # Send the topic
            response_join = ':%s TOPIC %s :%s' % (channel.topic_by, channel.name, channel.topic)
            self.send_queue.append(response_join)

            # Send join message to everybody in the channel, including yourself and
            # send user list of the channel back to the user.
            response_join = ':%s JOIN :%s' % (self.client_ident(), r_channel_name)
            for client in channel.clients:
                #if client != self: # FIXME: According to specs, this should be done because the user is included in the channel listing sent later.
                client.send_queue.append(response_join)

            nicks = [client.nick for client in channel.clients]
            response_userlist = ':%s 353 %s = %s :%s' % (self.server.servername, self.nick, channel.name, ' '.join(nicks))
            self.send_queue.append(response_userlist)

            response = ':%s 366 %s %s :End of /NAMES list' % (self.server.servername, self.nick, channel.name)
            self.send_queue.append(response)

    def handle_privmsg(self, params):
        """
        Handle sending a private message to a user or channel.
        """
        # FIXME: ERR_NEEDMOREPARAMS
        target, msg = params.split(' ', 1)

        message = ':%s PRIVMSG %s %s' % (self.client_ident(), target, msg)
        if target.startswith('#') or target.startswith('$'):
            # Message to channel. Check if the channel exists.
            channel = self.server.channels.get(target)
            if channel:
                if not channel.name in self.channels:
                    # The user isn't in the channel.
                    raise IRCError(ERR_CANNOTSENDTOCHAN, '%s :Cannot send to channel' % (channel.name))
                for client in channel.clients:
                    # Send message to all client in the channel, except the user himself.
                    # TODO: Abstract this into a seperate method so that not every function has
                    # to check if the user is in the channel.
                    if client != self:
                        client.send_queue.append(message)
            else:
                raise IRCError(ERR_NOSUCHNICK, 'PRIVMSG :%s' % (target))
        else:
            # Message to user
            client = self.server.clients.get(target, None)
            if client:
                client.send_queue.append(message)
            else:
                raise IRCError(ERR_NOSUCHNICK, 'PRIVMSG :%s' % (target))

    def handle_topic(self, params):
        """
        Handle a topic command.
        """
        if ' ' in params:
            channel_name = params.split(' ', 1)[0]
            topic = params.split(' ', 1)[1].lstrip(':')
        else:
            channel_name = params
            topic = None

        channel = self.server.channels.get(channel_name)
        if not channel:
            raise IRCError(ERR_NOSUCHNICK, 'PRIVMSG :%s' % (target))
        if not channel.name in self.channels:
            # The user isn't in the channel.
            raise IRCError(ERR_CANNOTSENDTOCHAN, '%s :Cannot send to channel' % (channel.name))

        if topic:
            channel.topic = topic
            channel.topic_by = self.nick
        message = ':%s TOPIC %s :%s' % (self.client_ident(), channel_name, channel.topic)
        return(message)

    def handle_part(self, params):
        """
        Handle a client parting from channel(s).
        """
        for pchannel in params.split(','):
            if pchannel.strip() in self.server.channels:
                # Send message to all clients in all channels user is in, and
                # remove the user from the channels.
                channel = self.server.channels.get(pchannel.strip())
                response = ':%s PART :%s' % (self.client_ident(), pchannel)
                if channel:
                    for client in channel.clients:
                        client.send_queue.append(response)
                channel.clients.remove(self)
                self.channels.pop(pchannel)
            else:
                response = ':%s 403 %s :%s' % (self.server.servername, pchannel, pchannel)
                self.send_queue.append(response)

    def handle_quit(self, params):
        """
        Handle the client breaking off the connection with a QUIT command.
        """
        response = ':%s QUIT :%s' % (self.client_ident(), params.lstrip(':'))
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

    def client_ident(self):
        """
        Return the client identifier as included in many command replies.
        """
        return('%s!%s@%s' % (self.nick, self.user, self.server.servername))

    def finish(self):
        """
        The client conection is finished. Do some cleanup to ensure that the
        client doesn't linger around in any channel or the client list, in case
        the client didn't properly close the connection with PART and QUIT.
        """
        logging.info('Client disconnected: %s' % (self.client_ident()))
        response = ':%s QUIT :EOF from client' % (self.client_ident())
        for channel in self.channels.values():
            if self in channel.clients:
                # Client is gone without properly QUITing or PARTing this
                # channel.
                for client in channel.clients:
                    client.send_queue.append(response)
                channel.clients.remove(self)
        self.server.clients.pop(self.nick)
        logging.info('Connection finished: %s' % (self.client_ident()))

    def __repr__(self):
        """
        Return a user-readable description of the client
        """
        return('<%s %s!%s@%s (%s)>' % (
            self.__class__.__name__,
            self.nick,
            self.user,
            self.host[0],
            self.realname,
            )
        )

class IRCServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass):
        self.servername = 'localhost'
        self.channels = {} # Existing channels (IRCChannel instances) by channelname
        self.clients = {}  # Connected clients (IRCClient instances) by nickname
        SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)

class Daemon:
    """
    Daemonize the current process (detach it from the console).
    """

    def __init__(self):
        # Fork a child and end the parent (detach from parent)
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0) # End parent
        except OSError, e:
            sys.stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(-2)

        # Change some defaults so the daemon doesn't tie up dirs, etc.
        os.setsid()
        os.umask(0)

        # Fork a child and end parent (so init now owns process)
        try:
            pid = os.fork()
            if pid > 0:
                try:
                    f = file('hircd.pid', 'w')
                    f.write(str(pid))
                    f.close()
                except IOError, e:
                    logging.error(e)
                    sys.stderr.write(repr(e))
                sys.exit(0) # End parent
        except OSError, e:
            sys.stderr.write("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(-2)

        # Close STDIN, STDOUT and STDERR so we don't tie up the controlling
        # terminal
        for fd in (0, 1, 2):
            try:
                os.close(fd)
            except OSError:
                pass

if __name__ == "__main__":
    #
    # Parameter parsing
    #
    parser = optparse.OptionParser()
    parser.set_usage(sys.argv[0] + " [option]")

    parser.add_option("--start", dest="start", action="store_true", default=True, help="Start hircd (default)")
    parser.add_option("--stop", dest="stop", action="store_true", default=False, help="Stop hircd")
    parser.add_option("--restart", dest="restart", action="store_true", default=False, help="Restart hircd")
    parser.add_option("-a", "--address", dest="listen_address", action="store", default='127.0.0.1', help="IP to listen on")
    parser.add_option("-p", "--port", dest="listen_port", action="store", default='6667', help="Port to listen on")
    parser.add_option("-V", "--verbose", dest="verbose", action="store_true", default=False, help="Be verbose (show lots of output)")
    parser.add_option("-l", "--log-stdout", dest="log_stdout", action="store_true", default=False, help="Also log to stdout")
    parser.add_option("-e", "--errors", dest="errors", action="store_true", default=False, help="Do not intercept errors.")
    parser.add_option("-f", "--foreground", dest="foreground", action="store_true", default=False, help="Do not go into daemon mode.")

    (options, args) = parser.parse_args()

    # Paths
    configfile = os.path.join(os.path.realpath(os.path.dirname(sys.argv[0])),'hircd.ini')
    logfile = os.path.join(os.path.realpath(os.path.dirname(sys.argv[0])),'hircd.log')

    #
    # Logging
    #
    if options.verbose:
        loglevel = logging.DEBUG
    else:
        loglevel = logging.WARNING

    log = logging.basicConfig(
        level=loglevel,
        format='%(asctime)s:%(levelname)s:%(message)s',
        filename=logfile,
        filemode='a')

    #
    # Handle start/stop/restart commands.
    #
    if options.stop or options.restart:
        pid = None
        try:
            f = file('hircd.pid', 'r')
            pid = int(f.readline())
            f.close()
            os.unlink('hircd.pid')
        except ValueError, e:
            sys.stderr.write('Error in pid file `hircd.pid`. Aborting\n')
            sys.exit(-1)
        except IOError, e:
            pass

        if pid:
            os.kill(pid, 15)
        else:
            sys.stderr.write('hircd not running or no PID file found\n')

        if not options.restart:
            sys.exit(0)

    logging.info("Starting hircd")
    logging.debug("configfile = %s" % (configfile))
    logging.debug("logfile = %s" % (logfile))

    if options.log_stdout:
        console = logging.StreamHandler()
        formatter = logging.Formatter('[%(levelname)s] %(message)s')
        console.setFormatter(formatter)
        console.setLevel(logging.DEBUG)
        logging.getLogger('').addHandler(console)

    if options.verbose:
        logging.info("We're being verbose")

    #
    # Go into daemon mode
    #
    if not options.foreground:
        Daemon()

    #
    # Start server
    #
    try:
        ircserver = IRCServer((options.listen_address, int(options.listen_port)), IRCClient)
        logging.info('Starting hircd on %s:%s' % (options.listen_address, options.listen_port))
        ircserver.serve_forever()
    except socket.error, e:
        logging.error(repr(e))
        sys.exit(-2)
