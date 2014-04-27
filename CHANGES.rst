Changes
-------

8.9
===

Documentation is now published at https://pythonhosted.org/irc.

8.8
===

* Issue #35: Removed the mutex during process_once.
* Issue #37: Deprecated buffer.LineBuffer for Python 3.

8.7
===

* Issue #34: Introduced ``buffer.LenientDecodingLineBuffer`` for handling
  input in a more lenient way, preferring UTF-8 but falling back to latin-1
  if the content cannot be decoded as UTF-8. To enable it by default for
  your application, set it as the default decoder::

    irc.client.ServerConnection.buffer_class = irc.buffer.LenientDecodingLineBuffer

8.6
===

* Introduced 'Manifold' as an alias for irc.client.IRC. This better name will
  replace the IRC name in a future version.
* Introduced the 'manifold' property of SimpleIRCClient as an alias for
  ircobj.
* Added 'manifold_class' property to the client.SimpleIRCClient to allow
  consumers to provide a customized Manifold.

8.5.4
=====

* Issue #32: Add logging around large DCC messages to facilitate
  troubleshooting.
* Issue #31: Fix error in connection wrapper for SSL example.

8.5.3
=====

* Issue #28: Fix TypeError in version calculation in irc.bot CTCP version.

8.5.2
=====

* Updated DCC send and receive scripts (Issue #27).

8.5.1
=====

* Fix timestamp support in ``schedule.DelayedCommand`` construction.

8.5
===

* ``irc.client.NickMask`` is now a Unicode object on Python 2. Fixes issue
  reported in pull request #19.
* Issue #24: Added `DCCConnection.send_bytes` for transmitting binary data.
  `privmsg` remains to support transmitting text.

8.4
===

* Code base now runs natively on Python 2 and Python 3, but requires `six
  <https://pypi.python.org/pypi/six>`_ to be installed.
* Issue #25: Rate-limiting has been updated to be finer grained (preventing
  bursts exceeding the limit following idle periods).

8.3.2
=====

* Issue #22: Catch error in bot.py on NAMREPLY when nick is not in any visible
  channel.

8.3.1
=====

* Fixed encoding errors in server on Python 3.

8.3
===

* Added a ``set_keepalive`` method to the ServerConnection. Sends a periodic
  PING message every indicated interval.

8.2
===

* Added support for throttling send_raw messages via the ServerConnection
  object. For example, on any connection object:

    connection.set_rate_limit(30)

  That would set the rate limit to 30 Hz (30 per second). Thanks to Jason
  Kendall for the suggestion and bug fixes.

8.1.2
=====

* Fix typo in `client.NickMask`.

8.1.1
=====

* Fix typo in bot.py.

8.1
===

* Issue #15: Added client support for ISUPPORT directives on server
  connections. Now, each ServerConnection has a `features` attribute which
  reflects the features supported by the server. See the docs for
  `irc.features` for details about the implementation.

8.0.1
=====

* Issue #14: Fix errors when handlers of the same priority are added under
  Python 3. This also fixes the unintended behavior of allowing handlers of
  the same priority to compare as unequal.

8.0
===

This release brings several backward-incompatible changes to the scheduled
commands.

* Refactored implementation of schedule classes. No longer do they override
  the datetime constructor, but now only provide suitable classmethods for
  construction in various forms.
* Removed backward-compatible references from irc.client.
* Remove 'arguments' parameter from scheduled commands.

Clients that reference the schedule classes from irc.client or that construct
them from the basic constructor will need to update to use the new class
methods::

  - DelayedCommand -> DelayedCommand.after
  - PeriodicCommand -> PeriodicCommand.after

Arguments may no longer be passed to the 'function' callback, but one is
encouraged instead to use functools.partial to attach parameters to the
callback. For example::

    DelayedCommand.after(3, func, ('a', 10))

becomes::

    func = functools.partial(func, 'a', 10)
    DelayedCommand.after(3, func)

This mode puts less constraints on the both the handler and the caller. For
example, a caller can now pass keyword arguments instead::

    func = functools.partial(func, name='a', quantity=10)
    DelayedCommand.after(3, func)

Readability, maintainability, and usability go up.

7.1.2
=====

* Issue #13: TypeError on Python 3 when constructing PeriodicCommand (and thus
  execute_every).

7.1.1
=====

* Fixed regression created in 7.0 where PeriodicCommandFixedDelay would only
  cause the first command to be scheduled, but not subsequent ones.

7.1
===

* Moved scheduled command classes to irc.schedule module. Kept references for
  backwards-compatibility.

7.0
===

* PeriodicCommand now raises a ValueError if it's created with a negative or
  zero delay (meaning all subsequent commands are immediately due). This fixes
  #12.
* Renamed the parameters to the IRC object. If you use a custom event loop
  and your code constructs the IRC object with keyword parameters, you will
  need to update your code to use the new names, so::

    IRC(fn_to_add_socket=adder, fn_to_remove_socket=remover, fn_to_add_timeout=timeout)

  becomes::

    IRC(on_connect=adder, on_disconnect=remover, on_schedule=timeout)

  If you don't use a custom event loop or you pass the parameters
  positionally, no change is necessary.

6.0.1
=====

* Fixed some unhandled exceptions in server client connections when the client
  would disconnect in response to messages sent after select was called.

6.0
===

* Moved `LineBuffer` and `DecodingLineBuffer` from client to buffer module.
  Backward-compatible references have been kept for now.
* Removed daemon mode and log-to-file options for server.
* Miscellaneous bugfixes in server.

5.1.1
=====

* Fix error in 2to3 conversion on irc/server.py (issue #11).

5.1
===

The IRC library is now licensed under the MIT license.

* Added irc/server.py, based on hircd by Ferry Boender.
* Added support for CAP command (pull request #10), thanks to Danneh Oaks.

5.0
===

Another backward-incompatible change. In irc 5.0, many of the unnecessary
getter functions have been removed and replaced with simple attributes. This
change addresses issue #2. In particular:

 - Connection._get_socket() -> Connection.socket (including subclasses)
 - Event.eventtype() -> Event.type
 - Event.source() -> Event.source
 - Event.target() -> Event.target
 - Event.arguments() -> Event.arguments

The `nm_to_*` functions were removed. Instead, use the NickMask class
attributes.

These deprecated function aliases were removed from irc.client::

 - parse_nick_modes -> modes.parse_nick_modes
 - parse_channel_modes -> modes.parse_channel_modes
 - generated_events -> events.generated
 - protocol_events -> events.protocol
 - numeric_events -> events.numeric
 - all_events -> events.all
 - irc_lower -> strings.lower

Also, the parameter name when constructing an event was renamed from
`eventtype` to simply `type`.

4.0
===

* Removed deprecated arguments to ServerConnection.connect. See notes on the
  3.3 release on how to use the connect_factory parameter if your application
  requires ssl, ipv6, or other connection customization.

3.6.1
=====

* Filter out disconnected sockets when processing input.

3.6
===

* Created two new exceptions in `irc.client`: `MessageTooLong` and
  `InvalidCharacters`.
* Use explicit exceptions instead of ValueError when sending data.

3.5
===

* SingleServerIRCBot now accepts keyword arguments which are passed through
  to the `ServerConnection.connect` method. One can use this to use SSL for
  connections::

    factory = irc.connection.Factory(wrapper=ssl.wrap_socket)
    bot = irc.bot.SingleServerIRCBot(..., connect_factory = factory)


3.4.2
=====

* Issue #6: Fix AttributeError when legacy parameters are passed to
  `ServerConnection.connect`.
* Issue #7: Fix TypeError on `iter(LineBuffer)`.

3.4.1
=====

3.4 never worked - the decoding customization feature was improperly
implemented and never tested.

* The ServerConnection now allows custom classes to be supplied to customize
  the decoding of incoming lines. For example, to disable the decoding of
  incoming lines,
  replace the `buffer_class` on the ServerConnection with a version that
  passes through the lines directly::

    irc.client.ServerConnection.buffer_class = irc.client.LineBuffer

  This fixes #5.

3.4
===

*Broken Release*

3.3
===

* Added `connection` module with a Factory for creating socket connections.
* Added `connect_factory` parameter to the ServerConnection.

It's now possible to create connections with custom SSL parameters or other
socket wrappers. For example, to create a connection with a custom SSL cert::

    import ssl
    import irc.client
    import irc.connection
    import functools

    irc = irc.client.IRC()
    server = irc.server()
    wrapper = functools.partial(ssl.wrap_socket, ssl_cert=my_cert())
    server.connect(connect_factory = irc.connection.Factory(wrapper=wrapper))

With this release, many of the parameters to `ServerConnection.connect` are
now deprecated:

    - localaddress
    - localport
    - ssl
    - ipv6

Instead, one should pass the appropriate values to a `connection.Factory`
instance and pass that factory to the .connect method. Backwards-compatibility
will be maintained for these parameters until the release of irc 4.0.

3.2.3
=====

* Restore Python 2.6 compatibility.

3.2.2
=====

* Protect from UnicodeDecodeError when decoding data on the wire when data is
  not properly encoded in ASCII or UTF-8.

3.2.1
=====

* Additional branch protected by mutex.

3.2
===

* Implemented thread safety via a reentrant lock guarding shared state in IRC
  objects.

3.1.1
=====

* Fix some issues with bytes/unicode on Python 3

3.1
===

* Distribute using setuptools rather than paver.
* Minor tweaks for Python 3 support. Now installs on Python 3.

3.0.1
=====

* Added error checking when sending a message - for both message length and
  embedded carriage returns. Fixes #4.
* Updated README.

3.0
===

* Improved Unicode support. Fixes failing tests and errors lowering Unicode
  channel names.
* Issue #3541414 - The ServerConnection and DCCConnection now encode any
  strings as UTF-8 before transmitting.
* Issue #3527371 - Updated strings.FoldedCase to support comparison against
  objects of other types.
* Shutdown the sockets before closing.

Applications that are currently encoding unicode as UTF-8 before passing the
strings to `ServerConnection.send_raw` need to be updated to send Unicode
or ASCII.

2.0.4
=====

This release officially deprecates 2.0.1-2.0.3 in favor of 3.0.

* Re-release of irc 2.0 (without the changes from 2.0.1-2.0.3) for
  correct compatibility indication.

2.0
===

* DelayedCommands now use the local time for calculating 'at' and 'due'
  times. This will be more friendly for simple servers. Servers that expect
  UTC times should either run in UTC or override DelayedCommand.now to
  return an appropriate time object for 'now'. For example::

    def startup_bot():
        irc.client.DelayedCommand.now = irc.client.DelayedCommand.utcnow
        ...

1.1
===

* Added irc.client.PeriodicCommandFixedDelay. Schedule this command
  to have a function executed at a specific time and then at periodic
  intervals thereafter.

1.0
===

* Removed `irclib` and `ircbot` legacy modules.

0.9
===

* Fix file saving using dccreceive.py on Windows. Fixes #2863199.
* Created NickMask class from nm_to_* functions. Now if a source is
  a NickMask, one can access the .nick, .host, and .user attributes.
* Use correct attribute for saved connect args. Fixes #3523057.

0.8
===

* Added ServerConnection.reconnect method. Fixes #3515580.

0.7.1
=====

* Added missing events. Fixes #3515578.

0.7
===

* Moved functionality from irclib module to irc.client module.
* Moved functionality from ircbot module to irc.bot module.
* Retained irclib and ircbot modules for backward-compatibility. These
  will be removed in 1.0.
* Renamed project to simply 'irc'.

To support the new module structure, simply replace references to the irclib
module with irc.client and ircbot module with irc.bot. This project will
support that interface through all versions of irc 1.x, so if you've made
these changes, you can safely depend on `irc >= 0.7, <2.0dev`.

0.6.3
=====

* Fixed failing test where DelayedCommands weren't being sorted properly.
  DelayedCommand a now subclass of the DateTime object, where the command's
  due time is the datetime. Fixed issue #3518508.

0.6.2
=====

* Fixed incorrect usage of Connection.execute_delayed (again).

0.6.0
=====

* Minimum Python requirement is now Python 2.6. Python 2.3 and earlier should use 0.5.0
  or earlier.
* Removed incorrect usage of Connection.execute_delayed. Added Connection.execute_every.
  Fixed issue 3516241.
* Use new-style classes.
