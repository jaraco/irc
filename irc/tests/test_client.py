from __future__ import print_function

from unittest import mock

import pytest
import six

import irc.client

def test_version():
	assert 'VERSION' in vars(irc.client)
	assert 'VERSION_STRING' in vars(irc.client)
	assert isinstance(irc.client.VERSION, tuple)
	assert irc.client.VERSION, "No VERSION detected."
	assert isinstance(irc.client.VERSION_STRING, six.string_types)

@mock.patch('irc.connection.socket')
def test_privmsg_sends_msg(socket_mod):
	server = irc.client.Reactor().server()
	server.connect('foo', 6667, 'bestnick')
	# make sure the mock object doesn't have a write method or it will treat
	#  it as an SSL connection and never call .send.
	del server.socket.write
	server.privmsg('#best-channel', 'You are great')
	server.socket.send.assert_called_with(
		b'PRIVMSG #best-channel :You are great\r\n')

@mock.patch('irc.connection.socket')
def test_privmsg_fails_on_embedded_carriage_returns(socket_mod):
	server = irc.client.Reactor().server()
	server.connect('foo', 6667, 'bestnick')
	with pytest.raises(ValueError):
		server.privmsg('#best-channel', 'You are great\nSo are you')

class TestHandlers(object):
	def test_handlers_same_priority(self):
		"""
		Two handlers of the same priority should still compare.
		"""
		handler1 = irc.client.PrioritizedHandler(1, lambda: None)
		handler2 = irc.client.PrioritizedHandler(1, lambda: 'other')
		assert not handler1 < handler2
		assert not handler2 < handler1

@mock.patch('irc.connection.socket')
def test_command_without_arguments(self):
	"A command without arguments should not crash"
	server = irc.client.Reactor().server()
	server.connect('foo', 6667, 'bestnick')
	server._process_line('GLOBALUSERSTATE')
