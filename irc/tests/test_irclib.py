import random

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
