#! /usr/bin/env python
#
# Example program using irc.client.
#
# servermap connects to an IRC server and finds out what other IRC
# servers there are in the net and prints a tree-like map of their
# interconnections.
#
# Example:
#
# % ./servermap irc.dal.net somenickname
# Connecting to server...
# Getting links...
#
# 26 servers (18 leaves and 8 hubs)
#
# splitrock.tx.us.dal.net
# `-vader.ny.us.dal.net
#   |-twisted.ma.us.dal.net
#   |-sodre.nj.us.dal.net
#   |-glass.oh.us.dal.net
#   |-distant.ny.us.dal.net
#   | |-algo.se.eu.dal.net
#   | | |-borg.se.eu.dal.net
#   | | | `-ced.se.eu.dal.net
#   | | |-viking.no.eu.dal.net
#   | | |-inco.fr.eu.dal.net
#   | | |-paranoia.se.eu.dal.net
#   | | |-gaston.se.eu.dal.net
#   | | | `-powertech.no.eu.dal.net
#   | | `-algo-u.se.eu.dal.net
#   | |-philly.pa.us.dal.net
#   | |-liberty.nj.us.dal.net
#   | `-jade.va.us.dal.net
#   `-journey.ca.us.dal.net
#     |-ion.va.us.dal.net
#     |-dragons.ca.us.dal.net
#     |-toronto.on.ca.dal.net
#     | `-netropolis-r.uk.eu.dal.net
#     |   |-traced.de.eu.dal.net
#     |   `-lineone.uk.eu.dal.net
#     `-omega.ca.us.dal.net

import argparse
import sys

import jaraco.logging

import irc.client


def on_connect(connection, event):
    sys.stdout.write("\nGetting links...")
    sys.stdout.flush()
    connection.links()


def on_passwdmismatch(connection, event):
    print("Password required.")
    sys.exit(1)


def on_links(connection, event):
    global links

    links.append((event.arguments[0],
                  event.arguments[1],
                  event.arguments[2]))


def on_endoflinks(connection, event):
    global links

    print("\n")

    m = {}
    for (to_node, from_node, desc) in links:
        if from_node != to_node:
            m[from_node] = m.get(from_node, []) + [to_node]

    if connection.get_server_name() in m:
        if len(m[connection.get_server_name()]) == 1:
            hubs = len(m) - 1
        else:
            hubs = len(m)
    else:
        hubs = 0

    print("%d servers (%d leaves and %d hubs)\n" % (
        len(links), len(links) - hubs, hubs))

    print_tree(0, [], connection.get_server_name(), m)
    connection.quit("Using irc.client.py")


def on_disconnect(connection, event):
    sys.exit(0)


def indent_string(level, active_levels, last):
    if level == 0:
        return ""
    s = ""
    for i in range(level - 1):
        if i in active_levels:
            s = s + "| "
        else:
            s = s + "  "
    if last:
        s = s + "`-"
    else:
        s = s + "|-"
    return s


def print_tree(level, active_levels, root, map, last=0):
    sys.stdout.write(indent_string(level, active_levels, last)
                     + root + "\n")
    if root in map:
        list = map[root]
        for r in list[:-1]:
            print_tree(level + 1, active_levels[:] + [level], r, map)
        print_tree(level + 1, active_levels[:], list[-1], map, 1)


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('server')
    parser.add_argument('nickname')
    parser.add_argument('-p', '--port', default=6667, type=int)
    jaraco.logging.add_arguments(parser)
    return parser.parse_args()


def main():
    global links

    args = get_args()
    jaraco.logging.setup(args)

    links = []

    reactor = irc.client.Reactor()
    sys.stdout.write("Connecting to server...")
    sys.stdout.flush()
    try:
        c = reactor.server().connect(args.server, args.port, args.nickname)
    except irc.client.ServerConnectionError as x:
        print(x)
        sys.exit(1)

    c.add_global_handler("welcome", on_connect)
    c.add_global_handler("passwdmismatch", on_passwdmismatch)
    c.add_global_handler("links", on_links)
    c.add_global_handler("endoflinks", on_endoflinks)
    c.add_global_handler("disconnect", on_disconnect)

    reactor.process_forever()


if __name__ == '__main__':
    main()
