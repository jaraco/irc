from __future__ import unicode_literals, absolute_import

from jaraco.collections import KeyTransformingDict

from . import strings


class IRCDict(KeyTransformingDict):
    """
    A dictionary of names whose keys are case-insensitive according to the
    IRC RFC rules.

    >>> d = IRCDict({'[This]': 'that'}, A='foo')

    The dict maintains the original case:

    >>> '[This]' in ''.join(d.keys())
    True

    But the keys can be referenced with a different case

    >>> d['a'] == 'foo'
    True

    >>> d['{this}'] == 'that'
    True

    >>> d['{THIS}'] == 'that'
    True

    >>> '{thiS]' in d
    True

    This should work for operations like delete and pop as well.

    >>> d.pop('A') == 'foo'
    True
    >>> del d['{This}']
    >>> len(d)
    0
    """

    @staticmethod
    def transform_key(key):
        if isinstance(key, str):
            key = strings.IRCFoldedCase(key)
        return key
