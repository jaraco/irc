VERSION := $(shell sed -n -e '/VERSION = /{s/VERSION = \(.*\), \(.*\), \(.*\)/\1.\2.\3/;p;}' <irclib.py)

all: doc

doc:
	rm -r doc
	mkdir doc
	PYTHONPATH=. pythondoc -d doc -f HTML4 -i frame=1 irclib ircbot

dist: doc
	mkdir python-irclib-$(VERSION)
	cp -r COPYING README ChangeLog Makefile irclib.py ircbot.py irccat \
	      irccat2 servermap testbot.py doc python-irclib-$(VERSION)
	tar cvzf python-irclib-$(VERSION).tar.gz python-irclib-$(VERSION)
	rm -r python-irclib-$(VERSION)

cvstag:
	cvs tag version_`echo $(VERSION) | sed 's/\./_/g'`

clean:
	rm -f *.tar.gz

.PHONY: all doc dist cvstag clean
