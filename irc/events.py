import itertools
import sys

from jaraco.text import clean, drop_comment, lines_from

if sys.version_info >= (3, 12):
    from importlib.resources import files
else:
    from importlib_resources import files


class Command(str):
    def __new__(cls, code, name):
        return super().__new__(cls, name)

    def __init__(self, code, name):
        self.code = code

    def __int__(self):
        return int(self.code)

    @staticmethod
    def lookup(raw) -> 'Command':
        """
        Lookup a command by numeric or by name.

        >>> Command.lookup('002')
        'yourhost'
        >>> Command.lookup('002').code
        '002'
        >>> int(Command.lookup('002'))
        2
        >>> int(Command.lookup('yourhost'))
        2
        >>> Command.lookup('yourhost').code
        '002'

        If a command is supplied that's an unrecognized name or code,
        a Command object is still returned.
        >>> fallback = Command.lookup('Unknown-command')
        >>> fallback
        'unknown-command'
        >>> fallback.code
        'unknown-command'
        >>> int(fallback)
        Traceback (most recent call last):
        ...
        ValueError: invalid literal for int() with base 10: 'unknown-command'
        >>> fallback = Command.lookup('999')
        >>> fallback
        '999'
        >>> int(fallback)
        999
        """
        fallback = Command(raw.lower(), raw.lower())
        return numeric.get(raw, _by_name.get(raw.lower(), fallback))


_codes = itertools.starmap(
    Command,
    map(
        str.split,
        map(drop_comment, clean(lines_from(files().joinpath('codes.txt')))),
    ),
)


numeric = {code.code: code for code in _codes}

codes = {v: k for k, v in numeric.items()}

_by_name = {v: v for v in numeric.values()}

generated = [
    "dcc_connect",
    "dcc_disconnect",
    "dccmsg",
    "disconnect",
    "ctcp",
    "ctcpreply",
    "login_failed",
]

protocol = [
    "error",
    "join",
    "kick",
    "mode",
    "part",
    "ping",
    "privmsg",
    "privnotice",
    "pubmsg",
    "pubnotice",
    "quit",
    "invite",
    "pong",
    "action",
    "topic",
    "nick",
]

all = generated + protocol + list(numeric.values())
