
# Library revamp changes

Changes of the cleanup:

  * **Removal of needless complexity of SimpleIRCClient -> Reactor -> ServerConnection**
    
    The reactor already manages multiple server connections similar to an
    overarching client class. Wrapping around a SimpleIRCClient which is then
    strangely limited to one single server is weird and not very useful.
    In addition, "Reactor" is a very unintuitive name for everyone not
    familiar with this exact pattern.

    Therefore, the Reactor was changed to Client with SimpleIRCClient removed
    to make the new chain of:

    Client -> ServerConnection

    (and the SimpleIRCClient class was removed entirely)

    Also, it is now much more trivial to connect to a server, and the library
    user no longer needs to keep track of their connections manually:

    ```
        client = irc.client.Client()
        client.add_global_handler("welcome",
            lambda connection, event: connection.privmsg("a_nickname",
                "Hi there!")
        ) # do this before add_server to ensure it's triggered
        client.add_server("irc.some.where", 6667, "my_own_nickname")
    ```

  * **Removal of process_once()/process_forever() explicit loop management**

    All the ServerConnection's now run their own processing in a thread. This
    removes the need for process_once()/process_forever(), all the
    documentation associated with it and allows any GTK/Tk user to easily run
    their own main loop as usual. This also means the user generally doesn't
    have to bother about the library's event loop at all.

    As a downside, registered handlers will now trigger in another thread, so
    the user needs to maintain basic thread-safety for their own application's
    callbacks.

  * **Delayed 001 / "welcome" event handler to wait for 004 and 005**

    The "welcome" event trigger is now delayed until 004 and 005 arrived (or
    a reasonable timeout for 005 has expired), which will ensure anyone simply
    subscribing to the "welcome" event to join channels will do so with all
    the basic server support info being received and properly processed.

  * **Adding tracking of joined channels and users in those channels**

    Almost any sort of non-trivial UI client or bot will need a reliable list
    of channels the client is inside, and the other users in there. Instead of
    putting functionality related to this into just the example bot in bot.py,
    this is now properly handled by the Client (previously Reactor) class.

  * **Moving of bot.py into irc/contrib/ and removal of server.py**

    The server implementation seems somewhat off-topic for a client protocol
    library. The bot implementation is also not really relevant to the core
    implementation, which is why it was moved into irc/contrib/


