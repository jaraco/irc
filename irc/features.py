class Features(object):
    """
    An implementation of features as loaded from an ISUPPORT server directive.

    Each feature is loaded into an attribute of the same name (but lowercased
    to match Python sensibilities).

    >>> f = Features()
    >>> f.load(['target', 'PREFIX=(abc)+-/', 'your message sir'])
    >>> f.prefix == {'+': 'a', '-': 'b', '/': 'c'}
    True
    """

    def __init__(self):
        self._set_rfc1459_prefixes()

    def _set_rfc1459_prefixes(self):
        "install standard (RFC1459) prefixes"
        self.set('PREFIX', {
            '@': 'o',
            '+': 'v',
        })

    def load(self, arguments):
        "Load the values from the a ServerConnection arguments"
        target, features, msg = arguments[:1], arguments[1:-1], arguments[-1:]
        map(self.load_feature, features)

    def remove(self, feature_name):
        if feature_name in vars(self):
            delattr(self, feature_name)

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
        return dict(zip(channel_chars, channel_modes))

    @staticmethod
    def _parse_CHANMODES(value):
        "channel mode letters"
        return value.split(',')

    @staticmethod
    def _parse_TARGMAX(value):
        return dict(
            (name, int(value) if value else None)
            for target in value.split(',')
            for name, value in target.split(':')
        )

    @staticmethod
    def _parse_CHANLIMIT(value):
        return dict(
            (target, int(number) if number else None)
            for target_split in value.split(',')
            for targets, number in target_split.split(':')
            for target in targets
        )
    _parse_MAXLIST = _parse_CHANLIMIT

    @staticmethod
    def _parse_other(value):
        if value.isdigit():
            return int(value)
        return value

    def set(self, name, value=True):
        "set a feature value"
        setattr(self, name.lower(), value)
