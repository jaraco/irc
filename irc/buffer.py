"""
Backward compatibility module.
"""

import warnings

from jaraco.stream.buffer import (
	LineBuffer,
	DecodingLineBuffer,
	LenientDecodingLineBuffer,
)

__all__ = [
	'LineBuffer',
	'DecodingLineBuffer',
	'LenientDecodingLineBuffer',
]

warnings.warn(
	"irc.buffer module will be removed "
	"in a future version. Use jaraco.stream.buffer instead.",
	DeprecationWarning,
)
