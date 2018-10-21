import collections


class FeatureSet:
    """
    An implementation of features as loaded from an ISUPPORT server directive.

    Each feature is loaded into an attribute of the same name (but lowercased
    to match Python sensibilities).

    >>> f = FeatureSet()
    >>> f.load(['target', 'PREFIX=(abc)+-/', 'your message sir'])
    >>> f.prefix == {'+': 'a', '-': 'b', '/': 'c'}
    True

    Order of prefix is relevant, so it is retained.

    >>> tuple(f.prefix)
    ('+', '-', '/')

    >>> f.load_feature('CHANMODES=foo,bar,baz')
    >>> f.chanmodes
    ['foo', 'bar', 'baz']
    """

    def __init__(self):
        self._set_rfc1459_prefixes()

    def _set_rfc1459_prefixes(self):
        "install standard (RFC1459) prefixes"
        self.set('PREFIX', {
            '@': 'o',
            '+': 'v',
        })

    def set(self, name, value=True):
        "set a feature value"
        setattr(self, name.lower(), value)

    def remove(self, feature_name):
        if feature_name in vars(self):
            delattr(self, feature_name)

    def load(self, arguments):
        "Load the values from the a ServerConnection arguments"
        features = arguments[1:-1]
        list(map(self.load_feature, features))

    def load_feature(self, feature):
        # negating
        if feature[0] == '-':
            return self.remove(feature[1:].lower())

        name, sep, value = feature.partition('=')

        if not sep:
            return

        if not value:
            self.set(name)
            return

        parser = getattr(self, '_parse_' + name, self._parse_other)
        value = parser(value)
        self.set(name, value)

    @staticmethod
    def _parse_PREFIX(value):
        "channel user prefixes"
        channel_modes, channel_chars = value.split(')')
        channel_modes = channel_modes[1:]
        return collections.OrderedDict(zip(channel_chars, channel_modes))

    @staticmethod
    def _parse_CHANMODES(value):
        "channel mode letters"
        return value.split(',')

    @staticmethod
    def _parse_TARGMAX(value):
        """
        >>> res = FeatureSet._parse_TARGMAX('a:3,c:,b:2')
        >>> res['a']
        3
        """
        return dict(
            string_int_pair(target, ':')
            for target in value.split(',')
        )

    @staticmethod
    def _parse_CHANLIMIT(value):
        """
        >>> res = FeatureSet._parse_CHANLIMIT('ibe:250,xyz:100')
        >>> len(res)
        6
        >>> res['x']
        100
        >>> res['i'] == res['b'] == res['e'] == 250
        True
        """
        pairs = map(string_int_pair, value.split(','))
        return dict(
            (target, number)
            for target_keys, number in pairs
            for target in target_keys
        )
    _parse_MAXLIST = _parse_CHANLIMIT

    @staticmethod
    def _parse_other(value):
        if value.isdigit():
            return int(value)
        return value


def string_int_pair(target, sep=':'):
    name, value = target.split(sep)
    value = int(value) if value else None
    return name, value
