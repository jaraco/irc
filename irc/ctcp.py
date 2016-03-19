from __future__ import absolute_import

'''
Internet Relay Chat (IRC) protocol client library.

Copyright © 1999-2002 Joel Rosdahl
Copyright © 2011-2016 Jason R. Coombs
Copyright © 2009 Ferry Boender
Copyright © 2016 Jonas Thiem

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
'''

"""
Handle Client-to-Client protocol per the `best available
spec <http://www.irchelp.org/irchelp/rfc/ctcpspec.html>`_.
"""

import re

LOW_LEVEL_QUOTE = '\x10'
LEVEL_QUOTE = "\\"
DELIMITER = '\x01'

low_level_mapping = {
    "0": '\x00',
    "n": "\n",
    "r": "\r",
    LEVEL_QUOTE: LEVEL_QUOTE
}

low_level_regexp = re.compile(LOW_LEVEL_QUOTE + "(.)")

def _low_level_replace(match_obj):
    ch = match_obj.group(1)

    # If low_level_mapping doesn't have the character as key, we
    # should just return the character.
    return low_level_mapping.get(ch, ch)


def dequote(message):
    """
    Dequote a message according to CTCP specifications.

    The function returns a list where each element can be either a
    string (normal message) or a tuple of one or two strings (tagged
    messages).  If a tuple has only one element (ie is a singleton),
    that element is the tag; otherwise the tuple has two elements: the
    tag and the data.

    Arguments:

        message -- The message to be decoded.
    """

    # Perform the substitution
    message = low_level_regexp.sub(_low_level_replace, message)

    if DELIMITER not in message:
        return [message]

    # Split it into parts.
    chunks = message.split(DELIMITER)

    return list(_gen_messages(chunks))


def _gen_messages(chunks):
    i = 0
    while i < len(chunks) - 1:
        # Add message if it's non-empty.
        if len(chunks[i]) > 0:
            yield chunks[i]

        if i < len(chunks) - 2:
            # Aye!  CTCP tagged data ahead!
            yield tuple(chunks[i + 1].split(" ", 1))

        i = i + 2

    if len(chunks) % 2 == 0:
        # Hey, a lonely _CTCP_DELIMITER at the end!  This means
        # that the last chunk, including the delimiter, is a
        # normal message!  (This is according to the CTCP
        # specification.)
        yield DELIMITER + chunks[-1]
