from __future__ import unicode_literals

import re

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

    >>> rb = DecodingLineBuffer()
    >>> b.errors = 'replace'
    >>> b.feed(b'Ol\xe9\n')
    >>> list(b.lines()) == [u'Ol\ufffd']
    True
    """
    encoding = 'utf-8'
    errors = 'strict'

    def lines(self):
        return (line.decode(self.encoding, self.errors)
            for line in super(DecodingLineBuffer, self).lines())
