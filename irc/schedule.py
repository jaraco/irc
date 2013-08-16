"""
Classes for calling functions a schedule.
"""

import datetime
import numbers

class DelayedCommand(datetime.datetime):
    """
    A command to be executed after some delay (seconds or timedelta).

    Clients may override .now() to have dates interpreted in a different
    manner, such as to use UTC or to have timezone-aware times.
    """
    @classmethod
    def now(self, tzinfo=None):
        return datetime.datetime.now(tzinfo)

    @classmethod
    def from_datetime(cls, other):
        return cls(other.year, other.month, other.day, other.hour,
            other.minute, other.second, other.microsecond,
            other.tzinfo)

    @classmethod
    def after(cls, delay, function):
        if not isinstance(delay, datetime.timedelta):
            delay = datetime.timedelta(seconds=delay)
        due_time = cls.now() + delay
        cmd = cls.from_datetime(due_time)
        cmd.delay = delay
        cmd.function = function
        return cmd

    @classmethod
    def at_time(cls, at, function):
        """
        Construct a DelayedCommand to come due at `at`, where `at` may be
        a datetime or timestamp. If `at` is a real number, it will be
        interpreted as a naive local timestamp.
        """
        if isinstance(at, numbers.Real):
            at = datetime.datetime.fromtimestamp(at)
        cmd = cls.from_datetime(at)
        cmd.delay = at - cmd.now()
        cmd.function = function
        return cmd

    def due(self):
        return self.now() >= self

class PeriodicCommand(DelayedCommand):
    """
    Like a delayed command, but expect this command to run every delay
    seconds.
    """
    def next(self):
        cmd = self.__class__.from_datetime(self + self.delay)
        cmd.delay = self.delay
        cmd.function = self.function
        return cmd

    def __setattr__(self, key, value):
        if key == 'delay' and not value > datetime.timedelta():
            raise ValueError("A PeriodicCommand must have a positive, "
                "non-zero delay.")
        super(PeriodicCommand, self).__setattr__(key, value)

class PeriodicCommandFixedDelay(PeriodicCommand):
    """
    Like a periodic command, but don't calculate the delay based on
    the current time. Instead use a fixed delay following the initial
    run.
    """

    @classmethod
    def at_time(cls, at, delay, function):
        if isinstance(at, int):
            at = datetime.datetime.fromtimestamp(at)
        cmd = cls.from_datetime(at)
        if not isinstance(delay, datetime.timedelta):
            delay = datetime.timedelta(seconds=delay)
        cmd.delay = delay
        cmd.function = function
        return cmd

    @classmethod
    def daily_at(cls, at, function):
        """
        Schedule a command to run at a specific time each day.
        """
        daily = datetime.timedelta(days=1)
        # convert when to the next datetime matching this time
        when = datetime.datetime.combine(datetime.date.today(), at)
        if when < cls.now():
            when += daily
        return cls.at_time(when, daily, function)
