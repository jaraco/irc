# -*- coding: utf-8 -*-

"""
Classes for calling functions a schedule.
"""

from __future__ import absolute_import

import datetime
import numbers

import pytz


def now():
    """
    Provide the current timezone-aware datetime.

    A client may override this function to change the default behavior,
    such as to use local time or timezone-naïve times.
    """
    return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)


def from_timestamp(ts):
    """
    Convert a numeric timestamp to a timezone-aware datetime.

    A client may override this function to change the default behavior,
    such as to use local time or timezone-naïve times.
    """
    return datetime.datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.utc)


class DelayedCommand(datetime.datetime):
    """
    A command to be executed after some delay (seconds or timedelta).
    """

    @classmethod
    def from_datetime(cls, other):
        return cls(other.year, other.month, other.day, other.hour,
            other.minute, other.second, other.microsecond,
            other.tzinfo)

    @classmethod
    def after(cls, delay, function):
        if not isinstance(delay, datetime.timedelta):
            delay = datetime.timedelta(seconds=delay)
        due_time = now() + delay
        cmd = cls.from_datetime(due_time)
        cmd.delay = delay
        cmd.function = function
        return cmd

    @staticmethod
    def _from_timestamp(input):
        """
        If input is a real number, interpret it as a Unix timestamp
        (seconds sinc Epoch in UTC) and return a timezone-aware
        datetime object. Otherwise return input unchanged.
        """
        if not isinstance(input, numbers.Real):
            return input
        return from_timestamp(input)

    @classmethod
    def at_time(cls, at, function):
        """
        Construct a DelayedCommand to come due at `at`, where `at` may be
        a datetime or timestamp.
        """
        at = cls._from_timestamp(at)
        cmd = cls.from_datetime(at)
        cmd.delay = at - now()
        cmd.function = function
        return cmd

    def due(self):
        return now() >= self


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
        at = cls._from_timestamp(at)
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
        if when < now():
            when += daily
        return cls.at_time(when, daily, function)
