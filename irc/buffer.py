from __future__ import unicode_literals, absolute_import

import re
import textwrap
import logging


log = logging.getLogger(__name__)


class LineBuffer(object):
    r"""
    Buffer bytes read in from a connection and serve complete lines back.

    >>> b = LineBuffer()
    >>> len(b)
    0

    >>> b.feed(b'foo\nbar')
    >>> len(b)
    7
    >>> list(b.lines()) == [b'foo']
    True
    >>> len(b)
    3

    >>> b.feed(b'bar\r\nbaz\n')
    >>> list(b.lines()) == [b'barbar', b'baz']
    True
    >>> len(b)
    0

    The buffer will not perform any decoding.

    >>> b.feed(b'Ol\xe9\n')
    >>> list(b.lines()) == [b'Ol\xe9']
    True

    The LineBuffer should also act as an iterable.

    >>> b.feed(b'iterate\nthis\n')
    >>> for line, expected in zip(b, [b'iterate', b'this']):
    ...    assert line == expected
    """
    line_sep_exp = re.compile(b'\r?\n')

    def __init__(self):
        self.buffer = b''

    def feed(self, bytes):
        self.buffer += bytes

    def lines(self):
        lines = self.line_sep_exp.split(self.buffer)
        # save the last, unfinished, possibly empty line
        self.buffer = lines.pop()
        return iter(lines)

    def __iter__(self):
        return self.lines()

    def __len__(self):
        return len(self.buffer)

class DecodingLineBuffer(LineBuffer):
    r"""
    Like LineBuffer, but decode the output (default assumes UTF-8).

    >>> utf8_word = b'Ol\xc3\xa9'
    >>> b = DecodingLineBuffer()
    >>> b.feed(b'bar\r\nbaz\n' + utf8_word + b'\n')
    >>> list(b.lines()) == ['bar', 'baz', utf8_word.decode('utf-8')]
    True
    >>> len(b)
    0

    Some clients will feed latin-1 or other encodings. If your client should
    support docoding from these clients (and not raise a UnicodeDecodeError),
    set errors='replace':

    >>> b = DecodingLineBuffer()
    >>> b.errors = 'replace'
    >>> b.feed(b'Ol\xe9\n')
    >>> list(b.lines()) == ['Ol\ufffd']
    True

    >>> b = DecodingLineBuffer()
    >>> b.feed(b'Ol\xe9\n')
    >>> list(b.lines())
    Traceback (most recent call last):
    ...
    UnicodeDecodeError: ...
    """
    encoding = 'utf-8'
    errors = 'strict'

    def lines(self):
        for line in super(DecodingLineBuffer, self).lines():
            try:
                yield line.decode(self.encoding, self.errors)
            except UnicodeDecodeError:
                self.handle_exception()

    def handle_exception(self):
        msg = textwrap.dedent("""
            Unknown encoding encountered. See 'Decoding Input'
            in https://pypi.python.org/pypi/irc for details.
            """)
        log.warning(msg)
        raise

class LenientDecodingLineBuffer(LineBuffer):
    r"""
    Like LineBuffer, but decode the output. First try UTF-8 and if that
    fails, use latin-1, which decodes all byte strings.

    >>> b = LenientDecodingLineBuffer()
    >>> utf8_word = b'Ol\xc3\xa9'
    >>> b.feed(utf8_word + b'\n')
    >>> b.feed(b'Ol\xe9\n')
    >>> list(b.lines()) == [utf8_word.decode('utf-8')]*2
    True
    """

    def lines(self):
        for line in super(LenientDecodingLineBuffer, self).lines():
            try:
                yield line.decode('utf-8', 'strict')
            except UnicodeDecodeError:
                yield line.decode('latin-1')
