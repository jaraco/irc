Internet Relay Chat (IRC) protocol client library
-------------------------------------------------

The home of irclib is:

* https://github.com/jaraco/irc

Documentation is available at:

* https://pythonhosted.org/irc

Change history is available at:

* https://pythonhosted.org/irc/history.html

You can `download project releases from PyPI
<https://pypi.python.org/pypi/irc>`_.

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

Features
========

The main features of the IRC client framework are:

* Handles multiple simultaneous IRC server connections
* Handles server PONGing transparently
* Optional external handling of the ``select()`` loop
* Event handling which allows custom handlers to be registered
* Decodes CTCP tagging correctly
* DCC connection support

Current limitations:

* The IRC protocol shines through the abstraction a bit too much.
* Data is not written asynchronously to the server (and DCC peers),
  i.e. the ``write()`` may block if the TCP buffers are stuffed.
* Like most projects, documentation is lacking ...

Getting started
===============

To get started, you can take a look at the examples. The simplest
example is ``irccat``.


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
  ``irc.contrib.bot``.  The bot enters a channel and listens for
  commands in private messages or channel traffic.  It also accepts
  DCC invitations and echos back sent DCC chat messages.

* ``dccreceive``

  Receives a file over DCC.

* ``dccsend``

  Sends a file over DCC.


NOTE: If you're running one of the examples on a unix command line, you need
to escape the ``#`` symbol in the channel. For example, use ``\\#test`` or
``"#test"`` instead of ``#test``.

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
Copyright © 2016 Jonas Thiem
