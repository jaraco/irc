VERSION := $(shell sed -n -e '/VERSION = /{s/VERSION = \(.*\), \(.*\), \(.*\)/\1.\2.\3/;p;}' <irclib.py)

all: doc

doc:
	rm -r doc
	mkdir doc
	PYTHONPATH=. pythondoc -d doc -f HTML4 -i frame=1 irclib

dist: doc
	mkdir irclib-$(VERSION)
	cp -r COPYING README ChangeLog Makefile irclib.py irccat servermap doc irclib-$(VERSION)
	tar cvzf irclib-$(VERSION).tar.gz irclib-$(VERSION)
	rm -r irclib-$(VERSION)

cvstag:
	cvs tag version_`echo $(VERSION) | sed 's/\./_/g'`

clean:
	rm -f *.tar.gz

.PHONY: all doc dist cvstag clean
