
class Tag(object):
    """
    An IRC message tag ircv3.net/specs/core/message-tags-3.2.html
    """
    @staticmethod
    def parse(item):
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
