from __future__ import print_function

class Tag(object):
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

        >>> print(Tag.parse('x=a\\nb\\nc')['value'])
        a
        b
        c
        """
        key, sep, value = item.partition('=')
        value = value.replace('\\:', ';')
        value = value.replace('\\s', ' ')
        value = value.replace('\\n', '\n')
        value = value.replace('\\r', '\r')
        value = value.replace('\\\\', '\\')
        value = value or None
        return {
            'key': key,
            'value': value,
        }
