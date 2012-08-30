import datetime
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
