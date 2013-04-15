from __future__ import print_function

import itertools
import time

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

class TestHandlers(object):
	def test_handlers_same_priority(self):
		"""
		Two handlers of the same priority should still compare.
		"""
		handler1 = irc.client.PrioritizedHandler(1, lambda: None)
		handler2 = irc.client.PrioritizedHandler(1, lambda: 'other')
		assert not handler1 < handler2
		assert not handler2 < handler1

class TestThrottler(object):
	def test_function_throttled(self):
		"""
		Ensure the throttler actually throttles calls.
		"""
		# set up a function to be called
		counter = itertools.count()
		# set up a version of `next` that is only called 30 times per second
		limited_next = irc.client.Throttler(next, 30)
		# for one second, call next as fast as possible
		deadline = time.time() + 1
		while time.time() < deadline:
			limited_next(counter)
		# ensure the counter was advanced about 30 times
		assert 29 <= next(counter) <= 31

	def test_reconstruct_unwraps(self):
		"""
		The throttler should be re-usable - if one wants to throttle a
		function that's aready throttled, the original function should be
		used.
		"""
		wrapped = irc.client.Throttler(next, 30)
		wrapped_again = irc.client.Throttler(wrapped, 60)
		assert wrapped_again.func is next
		assert wrapped_again.max_rate == 60
