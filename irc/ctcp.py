from __future__ import absolute_import

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

    def _low_level_replace(match_obj):
        ch = match_obj.group(1)

        # If low_level_mapping doesn't have the character as key, we
        # should just return the character.
        return low_level_mapping.get(ch, ch)

    if LOW_LEVEL_QUOTE in message:
        # Yup, there was a quote.  Release the dequoter, man!
        message = low_level_regexp.sub(_low_level_replace, message)

    if DELIMITER not in message:
        return [message]

    # Split it into parts.  (Does any IRC client actually *use*
    # CTCP stacking like this?)
    chunks = message.split(DELIMITER)

    messages = []
    i = 0
    while i < len(chunks) - 1:
        # Add message if it's non-empty.
        if len(chunks[i]) > 0:
            messages.append(chunks[i])

        if i < len(chunks) - 2:
            # Aye!  CTCP tagged data ahead!
            messages.append(tuple(chunks[i + 1].split(" ", 1)))

        i = i + 2

    if len(chunks) % 2 == 0:
        # Hey, a lonely _CTCP_DELIMITER at the end!  This means
        # that the last chunk, including the delimiter, is a
        # normal message!  (This is according to the CTCP
        # specification.)
        messages.append(DELIMITER + chunks[-1])

    return messages
