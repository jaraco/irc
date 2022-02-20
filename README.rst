.. image:: https://img.shields.io/pypi/v/irc.svg
   :target: `PyPI link`_

.. image:: https://img.shields.io/pypi/pyversions/irc.svg
   :target: `PyPI link`_

.. _PyPI link: https://pypi.org/project/irc

.. image:: https://github.com/jaraco/irc/workflows/tests/badge.svg
   :target: https://github.com/jaraco/irc/actions?query=workflow%3A%22tests%22
   :alt: tests

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/psf/black
   :alt: Code style: Black

.. image:: https://readthedocs.org/projects/python-irc/badge/?version=latest
   :target: https://python-irc.readthedocs.io/en/latest/?badge=latest

.. image:: https://img.shields.io/badge/skeleton-2022-informational
   :target: https://blog.jaraco.com/skeleton

.. image:: https://badges.gitter.im/jaraco/irc.svg
   :alt: Join the chat at https://gitter.im/jaraco/irc
   :target: https://gitter.im/jaraco/irc?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge

.. image:: https://tidelift.com/badges/github/jaraco/irc
   :target: https://tidelift.com/subscription/pkg/pypi-irc?utm_source=pypi-irc&utm_medium=referral&utm_campaign=readme

Full-featured Python IRC library for Python.

- `Project home <https://github.com/jaraco/irc>`_
- `Docs <https://python-irc.readthedocs.io/>`_
- `History <https://python-irc.readthedocs.io/en/latest/history.html>`_

Overview
========

This library provides a low-level implementation of the IRC protocol for
Python.  It provides an event-driven IRC client framework.  It has
a fairly thorough support for the basic IRC protocol, CTCP, and DCC
connections.

In order to understand how to make an IRC client, it's best to read up first
on the `IRC specifications
<http://web.archive.org/web/20160628193730/http://www.irchelp.org/irchelp/rfc/>`_.

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
* Multiple options for reading from and writing to an IRC server:
  you can use sockets in an internal ``select()`` loop OR use
  Python3's asyncio event loop
* Functions can be registered to execute at specified times by the
  event-loop.
* Decodes CTCP tagging correctly (hopefully); I haven't seen any
  other IRC client implementation that handles the CTCP
  specification subtleties.
* A kind of simple, single-server, object-oriented IRC client class
  that dispatches events to instance methods is included.
* DCC connection support.

Current limitations:

* The IRC protocol shines through the abstraction a bit too much.
* Data is not written asynchronously to the server (and DCC peers),
  i.e. the ``write()`` may block if the TCP buffers are stuffed.
* Like most projects, documentation is lacking ...
* DCC is not currently implemented in the asyncio-based version

Unfortunately, this library isn't as well-documented as I would like
it to be.  I think the best way to get started is to read and
understand the example program ``irccat``, which is included in the
distribution.

The following modules might be of interest:

* ``irc.client``

  The library itself.  Read the code along with comments and
  docstrings to get a grip of what it does.  Use it at your own risk
  and read the source, Luke!

* ``irc.client_aio``

  All the functionality of the above library, but utilizing
  Python 3's native asyncio library for the core event loop.
  Interface/API is otherwise functionally identical to the classes
  in ``irc.client``

* ``irc.bot``

  An IRC bot implementation.

* ``irc.server``

  A basic IRC server implementation. Suitable for testing, but not
  intended as a production service.

  Invoke the server with ``python -m irc.server``.

Examples
========

Example scripts in the scripts directory:

* ``irccat``

  A simple example of how to use the IRC client.  ``irccat`` reads
  text from stdin and writes it to a specified user or channel on
  an IRC server.

* ``irccat2``

  The same as above, but using the ``SimpleIRCClient`` class.

* ``aio_irccat``

  Same as above, but uses the asyncio-based event loop in
  ``AioReactor`` instead of the ``select()`` based ``Reactor``.


* ``aio_irccat2``

  Same as above, but using the ``AioSimpleIRCClient`` class


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

    server = irc.client.Reactor().server()
    server.buffer_class = buffer.LenientDecodingLineBuffer
    server.connect()

Alternatively, some clients may still want to decode the input using a
different encoding. To decode all input as latin-1 (which decodes any input),
use the following:

.. code:: python

    irc.client.ServerConnection.buffer_class.encoding = "latin-1"

Or decode to UTF-8, but use a replacement character for unrecognized byte
sequences:

.. code:: python

    irc.client.ServerConnection.buffer_class.errors = "replace"

Or, to simply ignore all input that cannot be decoded:

.. code:: python

    class IgnoreErrorsBuffer(buffer.DecodingLineBuffer):
        def handle_exception(self):
            pass


    irc.client.ServerConnection.buffer_class = IgnoreErrorsBuffer

The library requires text for message
processing, so a decoding buffer must be used. Clients
must use one of the above techniques for decoding input to text.

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

For Enterprise
==============

Available as part of the Tidelift Subscription.

This project and the maintainers of thousands of other packages are working with Tidelift to deliver one enterprise subscription that covers all of the open source you use.

`Learn more <https://tidelift.com/subscription/pkg/pypi-PROJECT?utm_source=pypi-PROJECT&utm_medium=referral&utm_campaign=github>`_.

Security Contact
================

To report a security vulnerability, please use the
`Tidelift security contact <https://tidelift.com/security>`_.
Tidelift will coordinate the fix and disclosure.
