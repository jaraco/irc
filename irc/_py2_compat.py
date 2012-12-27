from __future__ import absolute_import

import sys
import operator

__all__ = ['str', 'basestring', 'chr', 'socketserver', 'method_name']

py3 = sys.version_info >= (3,0)

if py3:
	str = basestring = str
	chr = chr
else:
	basestring = basestring
	str = unicode
	chr = unichr

try:
	import socketserver
except ImportError:
	import SocketServer as socketserver

method_name = operator.attrgetter('__name__' if py3 else 'func_name')
