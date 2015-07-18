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
        """
        if not group:
            return []

        a = group.split(" :", 1)
        arguments = a[0].split()
        if len(a) == 2:
            arguments.append(a[1])

        return arguments
