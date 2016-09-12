Internet Relay Chat (IRC) protocol client library
-------------------------------------------------

.. image:: https://badges.gitter.im/jaraco/irc.svg
   :alt: Join the chat at https://gitter.im/jaraco/irc
   :target: https://gitter.im/jaraco/irc?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge

.. image:: https://img.shields.io/pypi/v/irc.svg
   :target: https://pypi.org/project/irc

.. image:: https://img.shields.io/pypi/pyversions/irc.svg

.. image:: https://img.shields.io/pypi/dm/irc.svg

.. image:: https://img.shields.io/travis/jaraco/irc/master.svg
   :target: http://travis-ci.org/jaraco/irc

The home of irclib is:

* https://github.com/jaraco/irc

Documentation is available at:

* https://pythonhosted.org/irc

Change history is available at:

* https://pythonhosted.org/irc/history.html

You can `download project releases from PyPI
<https://pypi.io/project/irc>`_. The license is also indicated
there.

Tests are `continually run <https://travis-ci.org/#!/jaraco/irc>`_ using
Travis-CI.

|BuildStatus|_

.. |BuildStatus| image:: https://secure.travis-ci.org/jaraco/irc.png
.. _BuildStatus: https://travis-ci.org/jaraco/irc

This library provides a low-level implementation of the IRC protocol for
Python.  It provides an event-driven IRC client framework.  It has
a fairly thorough support for the basic IRC protocol, CTCP, and DCC
connections.

In order to understand how to make an IRC client, it's best to read up first
on the IRC specifications, available here:

* http://www.irchelp.org/irchelp/rfc/

Installation
============

IRC requires Python versions specified in the `download pages
<https://pypi.python.org/pypi/irc>`_ and definitely supports Python 3.

You have several options to install the IRC project.

* Use ``easy_install irc`` or ``pip install irc`` to grab the latest
  version from the cheeseshop (recommended).
* Run ``python setup.py install`` (from the source distribution).

Client Features
===============

The main features of the IRC client framework are:

* Abstraction of the IRC protocol.
* Handles multiple simultaneous IRC server connections.
* Handles server PONGing transparently.
* Messages to the IRC server are done by calling methods on an IRC
  connection object.
* Messages from an IRC server triggers events, which can be caught
  by event handlers.
* Reading from and writing to IRC server sockets is normally done
  by an internal ``select()`` loop, but the ``select()`` may be done
  by an external main loop.
* Functions can be registered to execute at specified times by the
  event-loop.
* Decodes CTCP tagging correctly (hopefully); I haven't seen any
  other IRC client implementation that handles the CTCP
  specification subtilties.
* A kind of simple, single-server, object-oriented IRC client class
  that dispatches events to instance methods is included.
* DCC connection support.

Current limitations:

* The IRC protocol shines through the abstraction a bit too much.
* Data is not written asynchronously to the server (and DCC peers),
  i.e. the ``write()`` may block if the TCP buffers are stuffed.
* Like most projects, documentation is lacking ...

Unfortunately, this library isn't as well-documented as I would like
it to be.  I think the best way to get started is to read and
understand the example program ``irccat``, which is included in the
distribution.

The following files might be of interest:

* ``irc/client.py``

  The library itself.  Read the code along with comments and
  docstrings to get a grip of what it does.  Use it at your own risk
  and read the source, Luke!

* ``irc/bot.py``

  An IRC bot implementation.

* ``irc/server.py``

  A basic IRC server implementation. Suitable for testing, but not
  production quality.

Examples
========

Example scripts in the scripts directory:

* ``irccat``

  A simple example of how to use the IRC client.  ``irccat`` reads
  text from stdin and writes it to a specified user or channel on
  an IRC server.

* ``irccat2``

  The same as above, but using the ``SimpleIRCClient`` class.

* ``servermap``

  Another simple example.  ``servermap`` connects to an IRC server,
  finds out what other IRC servers there are in the net and prints
  a tree-like map of their interconnections.

* ``testbot``

  An example bot that uses the ``SingleServerIRCBot`` class from
  ``irc.bot``.  The bot enters a channel and listens for commands in
  private messages or channel traffic.  It also accepts DCC
  invitations and echos back sent DCC chat messages.

* ``dccreceive``

  Receives a file over DCC.

* ``dccsend``

  Sends a file over DCC.


NOTE: If you're running one of the examples on a unix command line, you need
to escape the ``#`` symbol in the channel. For example, use ``\\#test`` or
``"#test"`` instead of ``#test``.


Scheduling Events
=================

The library includes a default event Scheduler as
``irc.schedule.DefaultScheduler``,
but this scheduler can be replaced with any other scheduler. For example,
to use the `schedule <https://pypi.org/project/schedule>`_ package,
include it
in your dependencies and install it into the IRC library as so:

    class ScheduleScheduler(irc.schedule.IScheduler):
        def execute_every(self, period, func):
            schedule.every(period).do(func)

        def execute_at(self, when, func):
            schedule.at(when).do(func)

        def execute_after(self, delay, func):
            raise NotImplementedError("Not supported")

        def run_pending(self):
            schedule.run_pending()

    irc.client.Reactor.scheduler_class = ScheduleScheduler


Decoding Input
==============

By default, the IRC library attempts to decode all incoming streams as
UTF-8, even though the IRC spec stipulates that no specific encoding can be
expected. Since assuming UTF-8 is not reasonable in the general case, the IRC
library provides options to customize decoding of input by customizing the
``ServerConnection`` class. The ``buffer_class`` attribute on the
``ServerConnection`` determines which class is used for buffering lines from the
input stream, using the ``buffer`` module in `jaraco.stream
<https://pypi.python.org/pypi/jaraco.stream>`_. By default it is
``buffer.DecodingLineBuffer``, but may be
re-assigned with another class, following the interface of ``buffer.LineBuffer``.
The ``buffer_class`` attribute may be assigned for all instances of
``ServerConnection`` by overriding the class attribute.

For example:

.. code:: python

    from jaraco.stream import buffer
    irc.client.ServerConnection.buffer_class = buffer.LenientDecodingLineBuffer

The ``LenientDecodingLineBuffer`` attempts UTF-8 but falls back to latin-1, which
will avoid ``UnicodeDecodeError`` in all cases (but may produce unexpected
behavior if an IRC user is using another encoding).

The buffer may be overridden on a per-instance basis (as long as it's
overridden before the connection is established):

.. code:: python

    server = irc.client.IRC().server()
    server.buffer_class = buffer.LenientDecodingLineBuffer
    server.connect()

Alternatively, some clients may still want to decode the input using a
different encoding. To decode all input as latin-1 (which decodes any input),
use the following:

.. code:: python

    irc.client.ServerConnection.buffer_class.encoding = 'latin-1'

Or decode to UTF-8, but use a replacement character for unrecognized byte
sequences:

.. code:: python

    irc.client.ServerConnection.buffer_class.errors = 'replace'

Or, to simply ignore all input that cannot be decoded:

.. code:: python

    class IgnoreErrorsBuffer(buffer.DecodingLineBuffer):
        def handle_exception(self):
            pass
    irc.client.ServerConnection.buffer_class = IgnoreErrorsBuffer

On Python 2, it was possible to use the ``buffer.LineBuffer`` itself, which will
pass the raw bytes. On Python 3, the library requires text for message
processing, so a decoding buffer must be used. Therefore, use of the
``LineBuffer`` is considered deprecated and not supported on Python 3. Clients
should use one of the above techniques for decoding input to text.

Notes and Contact Info
======================

Enjoy.

Maintainer:
Jason R. Coombs <jaraco@jaraco.com>

Original Author:
Joel Rosdahl <joel@rosdahl.net>

Copyright © 1999-2002 Joel Rosdahl
Copyright © 2011-2016 Jason R. Coombs
Copyright © 2009 Ferry Boender
