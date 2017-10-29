from __future__ import absolute_import, unicode_literals

import string

from jaraco.text import FoldedCase


class IRCFoldedCase(FoldedCase):
    """
    A version of FoldedCase that honors the IRC specification for lowercased
    strings (RFC 1459).

    >>> IRCFoldedCase('Foo^').lower()
    'foo~'

    >>> IRCFoldedCase('[this]') == IRCFoldedCase('{THIS}')
    True

    >>> IRCFoldedCase().lower()
    ''
    """
    translation = dict(zip(
        map(ord, string.ascii_uppercase + r"[]\^"),
        map(ord, string.ascii_lowercase + r"{}|~"),
    ))

    def lower(self):
        return (
            self.translate(self.translation) if self
            # bypass translate, which returns self
            else super(IRCFoldedCase, self).lower()
        )


def lower(str):
    return IRCFoldedCase(str).lower()
