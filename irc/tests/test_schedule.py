import random
import datetime

import pytest

from irc import schedule


def test_delayed_command_order():
	"""
	delayed commands should be sorted by delay time
	"""
	null = lambda: None
	delays = [random.randint(0, 99) for x in range(5)]
	cmds = sorted([
		schedule.DelayedCommand(delay, null, tuple())
		for delay in delays
	])
	assert [c.delay.seconds for c in cmds] == sorted(delays)

def test_periodic_command_delay():
	"A PeriodicCommand must have a positive, non-zero delay."
	with pytest.raises(ValueError) as exc_info:
		schedule.PeriodicCommand(0, None, None)
	assert str(exc_info.value) == test_periodic_command_delay.__doc__

def test_periodic_command_fixed_delay():
	"""
	Test that we can construct a periodic command with a fixed initial
	delay.
	"""
	fd = schedule.PeriodicCommandFixedDelay.at_time(
		at = datetime.datetime.now(),
		delay = datetime.timedelta(seconds=2),
		function = lambda: None,
		arguments = [],
		)
	assert fd.due() == True
	assert fd.next().due() == False
