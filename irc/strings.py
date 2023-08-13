from jaraco.text import FoldedCase


class IRCFoldedCase(FoldedCase):
    """
    A version of FoldedCase that honors the IRC specification for lowercased
    strings (RFC 1459).

    >>> IRCFoldedCase('Foo^').lower()
    'foo~'

    >>> IRCFoldedCase('[this]') == IRCFoldedCase('{THIS}')
    True

    >>> IRCFoldedCase('[This]').casefold()
    '{this}'

    >>> IRCFoldedCase().lower()
    ''
    """

    translation = dict(
        zip(
            map(ord, r"[]\^"),
            map(ord, r"{}|~"),
        )
    )

    def lower(self):
        return super().lower().translate(self.translation)

    def casefold(self):
        """
        Ensure cached superclass value doesn't supersede.

        >>> ob = IRCFoldedCase('[This]')
        >>> ob.casefold()
        '{this}'
        >>> ob.casefold()
        '{this}'
        """
        return super().casefold().translate(self.translation)

    def __setattr__(self, key, val):
        if key == 'casefold':
            return
        return super().__setattr__(key, val)


def lower(str):
    return IRCFoldedCase(str).lower()
