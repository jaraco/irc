from __future__ import absolute_import

try:
	str = unicode
except NameError:
	str = str

try:
	import socketserver
except ImportError:
	import SocketServer as socketserver
