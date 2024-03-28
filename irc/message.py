import re

_TAG_UNESCAPE_RE = re.compile(r'\\(.)')
_TAG_UNESCAPE_MAP = {':': ';', 's': ' ', 'n': '\n', 'r': '\r', '\\': '\\'}


class Tag:
    """
    An IRC message tag ircv3.net/specs/core/message-tags-3.2.html
    """

    @staticmethod
    def parse(item):
        r"""
        >>> Tag.parse('x') == {'key': 'x', 'value': None}
        True

        >>> Tag.parse('x=yes') == {'key': 'x', 'value': 'yes'}
        True

        >>> Tag.parse('x=3')['value']
        '3'

        >>> Tag.parse('x=red fox\\:green eggs')['value']
        'red fox;green eggs'

        >>> Tag.parse('x=red fox:green eggs')['value']
        'red fox:green eggs'

        >>> Tag.parse('x=a\\nb\\nc')['value']
        'a\nb\nc'

        >>> Tag.parse(r'x=a\bb\bc')['value']
        'abbbc'

        >>> Tag.parse(r'x=a\\nb\\nc')['value']
        'a\\nb\\nc'
        """
        key, sep, value = item.partition('=')
        value = _TAG_UNESCAPE_RE.sub(
            lambda char: _TAG_UNESCAPE_MAP.get(char.group(1), char.group(1)), value
        )
        value = value or None
        return {'key': key, 'value': value}

    @classmethod
    def from_group(cls, group):
        """
        Construct tags from the regex group
        """
        if not group:
            return
        tag_items = group.split(";")
        return list(map(cls.parse, tag_items))


class Arguments(list):
    @staticmethod
    def from_group(group):
        """
        Construct arguments from the regex group

        >>> Arguments.from_group('foo')
        ['foo']

        >>> Arguments.from_group(None)
        []

        >>> Arguments.from_group('')
        []

        >>> Arguments.from_group('foo bar')
        ['foo', 'bar']

        >>> Arguments.from_group('foo bar :baz')
        ['foo', 'bar', 'baz']

        >>> Arguments.from_group('foo bar :baz bing')
        ['foo', 'bar', 'baz bing']
        """
        if not group:
            return []

        main, sep, ext = group.partition(" :")
        arguments = main.split()
        if sep:
            arguments.append(ext)

        return arguments
