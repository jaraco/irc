from __future__ import absolute_import

import re
import string

# from jaraco.util.string
class FoldedCase(str):
    """
    A case insensitive string class; behaves just like str
    except compares equal when the only variation is case.
    >>> s = FoldedCase('hello world')

    >>> s == 'Hello World'
    True

    >>> 'Hello World' == s
    True

    >>> s.index('O')
    4

    >>> s.split('O')
    ['hell', ' w', 'rld']

    >>> names = map(FoldedCase, ['GAMMA', 'alpha', 'Beta'])
    >>> names.sort()
    >>> names
    ['alpha', 'Beta', 'GAMMA']
    """
    def __lt__(self, other):
        return self.lower() < other.lower()

    def __gt__(self, other):
        return self.lower() > other.lower()

    def __eq__(self, other):
        return self.lower() == other.lower()

    def __hash__(self):
        return hash(self.lower())

    # cache lower since it's likely to be called frequently.
    def lower(self):
        self._lower = super(FoldedCase, self).lower()
        self.lower = lambda: self._lower
        return self._lower

    def index(self, sub):
        return self.lower().index(sub.lower())

    def split(self, splitter=' ', maxsplit=0):
        pattern = re.compile(re.escape(splitter), re.I)
        return pattern.split(self, maxsplit)

class IRCFoldedCase(FoldedCase):
    """
    A version of FoldedCase that honors the IRC specification for lowercased
    strings (RFC 1459).

    >>> IRCFoldedCase('Foo^').lower()
    'foo~'
    >>> IRCFoldedCase('[this]') == IRCFoldedCase('{THIS}')
    True
    """
    translation = string.maketrans(
        string.ascii_uppercase + r"[]\^",
        string.ascii_lowercase + r"{}|~",
    )

    def lower(self):
        return self.translate(self.translation)

def lower(str):
    return IRCFoldedCase(str).lower()
