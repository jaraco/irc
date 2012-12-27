from __future__ import unicode_literals

from . import strings
from . import _py2_compat

# from jaraco.util.dictlib
class KeyTransformingDict(dict):
    """
    A dict subclass that transforms the keys before they're used.
    Subclasses may override the default key_transform to customize behavior.
    """
    @staticmethod
    def key_transform(key):
        return key

    def __init__(self, *args, **kargs):
        super(KeyTransformingDict, self).__init__()
        # build a dictionary using the default constructs
        d = dict(*args, **kargs)
        # build this dictionary using transformed keys.
        for item in d.items():
            self.__setitem__(*item)

    def __setitem__(self, key, val):
        key = self.key_transform(key)
        super(KeyTransformingDict, self).__setitem__(key, val)

    def __getitem__(self, key):
        key = self.key_transform(key)
        return super(KeyTransformingDict, self).__getitem__(key)

    def __contains__(self, key):
        key = self.key_transform(key)
        return super(KeyTransformingDict, self).__contains__(key)

    def __delitem__(self, key):
        key = self.key_transform(key)
        return super(KeyTransformingDict, self).__delitem__(key)

    def setdefault(self, key, *args, **kwargs):
        key = self.key_transform(key)
        return super(KeyTransformingDict, self).setdefault(key, *args, **kwargs)

    def pop(self, key, *args, **kwargs):
        key = self.key_transform(key)
        return super(KeyTransformingDict, self).pop(key, *args, **kwargs)

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
    def key_transform(key):
        if isinstance(key, _py2_compat.basestring):
            key = strings.IRCFoldedCase(key)
        return key
