import datetime
import random

import pytest
import mock

import irc.client

def test_version():
	assert 'VERSION' in vars(irc.client)
	assert isinstance(irc.client.VERSION, tuple)
	assert irc.client.VERSION, "No VERSION detected."

def test_delayed_command_order():
	"""
	delayed commands should be sorted by delay time
	"""
	null = lambda: None
	delays = [random.randint(0, 99) for x in xrange(5)]
	cmds = sorted([
		irc.client.DelayedCommand(delay, null, tuple())
		for delay in delays
	])
	assert [c.delay.seconds for c in cmds] == sorted(delays)

def test_periodic_command_fixed_delay():
	"""
	Test that we can construct a periodic command with a fixed initial
	delay.
	"""
	fd = irc.client.PeriodicCommandFixedDelay.at_time(
		at = datetime.datetime.now(),
		delay = datetime.timedelta(seconds=2),
		function = lambda: None,
		arguments = [],
		)
	assert fd.due() == True
	assert fd.next().due() == False

@mock.patch('irc.client.socket')
def test_privmsg_sends_msg(socket_mod):
	server = irc.client.IRC().server()
	server.connect('foo', 6667, 'bestnick')
	server.privmsg('#best-channel', 'You are great')
	socket_mod.socket.return_value.send.assert_called_with(
		'PRIVMSG #best-channel :You are great\r\n')

@mock.patch('irc.client.socket')
def test_privmsg_fails_on_embedded_carriage_returns(socket_mod):
	server = irc.client.IRC().server()
	server.connect('foo', 6667, 'bestnick')
	with pytest.raises(ValueError):
		server.privmsg('#best-channel', 'You are great\nSo are you')
