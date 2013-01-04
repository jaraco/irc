import datetime
import random

import pytest
import mock

import irc.client

def test_version():
	assert 'VERSION' in vars(irc.client)
	assert isinstance(irc.client.VERSION, tuple)
	assert irc.client.VERSION, "No VERSION detected."

@mock.patch('irc.connection.socket')
def test_privmsg_sends_msg(socket_mod):
	server = irc.client.IRC().server()
	server.connect('foo', 6667, 'bestnick')
	# make sure the mock object doesn't have a write method or it will treat
	#  it as an SSL connection and never call .send.
	del server.socket.write
	server.privmsg('#best-channel', 'You are great')
	server.socket.send.assert_called_with(
		b'PRIVMSG #best-channel :You are great\r\n')

@mock.patch('irc.connection.socket')
def test_privmsg_fails_on_embedded_carriage_returns(socket_mod):
	server = irc.client.IRC().server()
	server.connect('foo', 6667, 'bestnick')
	with pytest.raises(ValueError):
		server.privmsg('#best-channel', 'You are great\nSo are you')
