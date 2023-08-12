def parse_nick_modes(mode_string):
    """Parse a nick mode string.

    The function returns a list of lists with three members: sign,
    mode and argument.  The sign is "+" or "-".  The argument is
    always None.

    Example:

    >>> parse_nick_modes("+ab-c")
    [['+', 'a', None], ['+', 'b', None], ['-', 'c', None]]
    """

    return _parse_modes(mode_string, "")


def parse_channel_modes(mode_string):
    """Parse a channel mode string.

    The function returns a list of lists with three members: sign,
    mode and argument.  The sign is "+" or "-".  The argument is
    None if mode isn't one of "b", "k", "l", "v", "o", "h", or "q".

    Example:

    >>> parse_channel_modes("+ab-c foo")
    [['+', 'a', None], ['+', 'b', 'foo'], ['-', 'c', None]]
    """
    return _parse_modes(mode_string, "bklvohq")


def _parse_modes(mode_string, unary_modes=""):
    """
    Parse the mode_string and return a list of triples.

    If no string is supplied return an empty list.

    >>> _parse_modes('')
    []

    If no sign is supplied, return an empty list.

    >>> _parse_modes('ab')
    []

    Discard unused args.

    >>> _parse_modes('+a foo bar baz')
    [['+', 'a', None]]

    Return none for unary args when not provided

    >>> _parse_modes('+abc foo', unary_modes='abc')
    [['+', 'a', 'foo'], ['+', 'b', None], ['+', 'c', None]]

    This function never throws an error:

    >>> import random
    >>> def random_text(min_len = 3, max_len = 80):
    ...     len = random.randint(min_len, max_len)
    ...     chars_to_choose = [chr(x) for x in range(0,1024)]
    ...     chars = (random.choice(chars_to_choose) for x in range(len))
    ...     return ''.join(chars)
    >>> def random_texts(min_len = 3, max_len = 80):
    ...     while True:
    ...         yield random_text(min_len, max_len)
    >>> import itertools
    >>> texts = itertools.islice(random_texts(), 1000)
    >>> set(type(_parse_modes(text)) for text in texts) == {list}
    True
    """

    # mode_string must be non-empty and begin with a sign
    if not mode_string or mode_string[0] not in "+-":
        return []

    modes = []

    parts = mode_string.split()

    mode_part, args = parts[0], parts[1:]

    for ch in mode_part:
        if ch in "+-":
            sign = ch
            continue
        arg = args.pop(0) if ch in unary_modes and args else None
        modes.append([sign, ch, arg])
    return modes
