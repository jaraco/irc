class Features(object):
    """
    An implementation of features as loaded from an ISUPPORT server directive.
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

        if value:
            self._set_special(name, value)
        else:
            self.set(name)

    def _set_special(self, name, value):
        if name == 'PREFIX':  # channel user prefixes
            channel_modes, channel_chars = value.split(')')
            channel_modes = channel_modes[1:]
            self.set(name, {})
            for i in range(len(channel_modes)):
                self.prefix[channel_modes[i]] = channel_chars[i]

        elif name == 'CHANMODES':
            # channel mode letters
            self.set(name, value.split(','))

        elif name == 'TARGMAX':
            self.set(name, {})

            for target in value.split(','):
                target_name, target_value = target.split(':')
                if target_value == '':
                    target_value = None
                else:
                    target_value = int(target_value)
                self.targmax[target_name] = target_value

        elif name in ['CHANLIMIT', 'MAXLIST']:
            res = {}
            self.set(name, res)

            for target_split in value.split(','):
                targets, number = target_split.split(':')

                if number == '':
                    number = None
                else:
                    number = int(number)

                for target in targets:
                    res[target] = number

        elif value.isdigit():
            self.set(name, int(value))

        else:
            self.set(name, value)

    def set(self, name, value=True):
        "set a feature value"
        setattr(self, name.lower(), value)
