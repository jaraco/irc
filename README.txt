hircd - Hacky IRC Daemon
========================

About
-----

hircd is a minimal, hacky implementation of an IRC server daemon written in
Python in about 400 lines of code, including comments, etc.

It only has (sometimes basic) support for:

* Connecting
* Channels
* Nicknames
* Public/private messages

It is MISSING support for notably:

* Server linking
* Modes (user and channel)
* Proper error reporting
* Basically everything else

It is mostly useful as a testing tool or perhaps for building something like a
private proxy on. Do NOT use it in any kind of production code or anything that
will ever be connected to by the public.

Usage
-----

	Usage: ./hircd.py [option]

	Options:
	  -h, --help            show this help message and exit
	  --start               Start hircd (default)
	  --stop                Stop hircd
	  --restart             Restart hircd
	  -a LISTEN_ADDRESS, --address=LISTEN_ADDRESS
							IP to listen on
	  -p LISTEN_PORT, --port=LISTEN_PORT
							Port to listen on
	  -V, --verbose         Be verbose (show lots of output)
	  -l, --log-stdout      Also log to stdout
	  -e, --errors          Do not intercept errors.
	  -f, --foreground      Do not go into daemon mode.

Copyright
---------

hircd is Copyright by Ferry Boender, 2009 - Released under the MIT License

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

