from __future__ import absolute_import, unicode_literals

import string

from jaraco.text import FoldedCase

class IRCFoldedCase(FoldedCase):
    """
    A version of FoldedCase that honors the IRC specification for lowercased
    strings (RFC 1459).

    >>> print(IRCFoldedCase('Foo^').lower())
    foo~

    >>> IRCFoldedCase('[this]') == IRCFoldedCase('{THIS}')
    True

    >>> IRCFoldedCase().lower() == ''
    True
    """
    translation = dict(zip(
        map(ord, string.ascii_uppercase + r"[]\^"),
        map(ord, string.ascii_lowercase + r"{}|~"),
    ))

    def lower(self):
        if not self:
            # bypass translate, which returns self
            return super(IRCFoldedCase, self).lower()
        return self.translate(self.translation)

def lower(str):
    return IRCFoldedCase(str).lower()
