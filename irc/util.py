from __future__ import division, absolute_import

def total_seconds(td):
    """
    Python 2.7 adds a total_seconds method to timedelta objects.
    See http://docs.python.org/library/datetime.html#datetime.timedelta.total_seconds

    >>> import datetime
    >>> total_seconds(datetime.timedelta(hours=24))
    86400.0
    """
    try:
        result = td.total_seconds()
    except AttributeError:
        seconds = td.seconds + td.days * 24 * 3600
        result = (td.microseconds + seconds * 10**6) / 10**6
    return result
