VERSION := $(shell sed -n -e '/VERSION = /{s/VERSION = \(.*\), \(.*\), \(.*\)/\1.\2.\3/;p;}' <irclib.py)

main:
	@echo "Nothing to be made."

dist:
	mkdir irclib-$(VERSION)
	cp COPYING README ChangeLog Makefile irclib.py ircbot.py irccat servermap irclib-$(VERSION)
	tar cvzf irclib-$(VERSION).tar.gz irclib-$(VERSION)
	rm -r irclib-$(VERSION)

cvstag:
	cvs tag version_`echo $(VERSION) | sed 's/\./_/g'`

clean:
	rm -f *.tar.gz
