from __future__ import absolute_import

import sys
import operator

__all__ = ['str', 'socketserver', 'method_name']

py3 = sys.version_info >= (3,0)

try:
	str = unicode
except NameError:
	str = str

try:
	import socketserver
except ImportError:
	import SocketServer as socketserver

method_name = operator.attrgetter('__name__' if py3 else 'func_name')
