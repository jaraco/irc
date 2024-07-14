import itertools
from importlib.resources import files

from jaraco.text import clean, drop_comment, lines_from


class Code(str):
    def __new__(cls, code, name):
        return super().__new__(cls, name)

    def __init__(self, code, name):
        self.code = code

    def __int__(self):
        return int(self.code)


_codes = itertools.starmap(
    Code,
    map(
        str.split,
        map(drop_comment, clean(lines_from(files().joinpath('codes.txt')))),
    ),
)


numeric = {code.code: code for code in _codes}

codes = {v: k for k, v in numeric.items()}

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
