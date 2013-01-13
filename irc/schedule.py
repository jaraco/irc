"""
Classes for calling functions a schedule.
"""

import datetime

class DelayedCommand(datetime.datetime):
    """
    A command to be executed after some delay (seconds or timedelta).

    Clients may override .now() to have dates interpreted in a different
    manner, such as to use UTC or to have timezone-aware times.
    """
    def __init__(self, delay, function, arguments):
        pass

    def __new__(cls, delay, function, arguments):
        if not isinstance(delay, datetime.timedelta):
            delay = datetime.timedelta(seconds=delay)
        at = cls.now() + delay
        cmd = datetime.datetime.__new__(cls, at.year,
            at.month, at.day, at.hour, at.minute, at.second,
            at.microsecond, at.tzinfo)
        cmd.delay = delay
        cmd.function = function
        cmd.arguments = arguments
        return cmd

    @classmethod
    def now(self, tzinfo=None):
        return datetime.datetime.now(tzinfo)

    @classmethod
    def at_time(cls, at, function, arguments):
        """
        Construct a DelayedCommand to come due at `at`, where `at` may be
        a datetime or timestamp. If `at` is a timestamp, it will be
        interpreted as a naive local timestamp.
        """
        if isinstance(at, int):
            at = datetime.datetime.fromtimestamp(at)
        delay = at - cls.now()
        return cls(delay, function, arguments)

    def due(self):
        return self.now() >= self

class PeriodicCommandBase(DelayedCommand):
    def next(self):
        return PeriodicCommand(self.delay, self.function,
            self.arguments)

    def _check_delay(self):
        if not self.delay > datetime.timedelta():
            raise ValueError("A PeriodicCommand must have a positive, "
                "non-zero delay.")

class PeriodicCommand(PeriodicCommandBase):
    """
    Like a delayed command, but expect this command to run every delay
    seconds.
    """
    def __init__(self, *args, **kwargs):
        super(PeriodicCommand, self).__init__(*args, **kwargs)
        self._check_delay()

class PeriodicCommandFixedDelay(PeriodicCommandBase):
    """
    Like a periodic command, but don't calculate the delay based on
    the current time. Instead use a fixed delay following the initial
    run.
    """

    @classmethod
    def at_time(cls, at, delay, function, arguments):
        cmd = super(PeriodicCommandFixedDelay, cls).at_time(
            at, function, arguments)
        if not isinstance(delay, datetime.timedelta):
            delay = datetime.timedelta(seconds=delay)
        cmd.delay = delay
        cmd._check_delay()
        return cmd
