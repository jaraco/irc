VERSION := $(shell sed -n -e '/VERSION = /{s/VERSION = \(.*\), \(.*\), \(.*\)/\1.\2.\3/;p;}' <irclib.py)

DISTFILES = \
    COPYING \
    ChangeLog \
    Makefile \
    README \
    dccreceive \
    dccsend \
    ircbot.py \
    irccat \
    irccat2 \
    irclib.py \
    servermap \
    setup.py \
    testbot.py

PACKAGENAME = python-irclib-$(VERSION)

all:
	echo "Nothing to do."

dist:
	mkdir $(PACKAGENAME)
	cp -r $(DISTFILES) $(PACKAGENAME)
	tar cvzf $(PACKAGENAME).tar.gz $(PACKAGENAME)
	zip -r9yq $(PACKAGENAME).tar.gz $(PACKAGENAME)
	rm -r $(PACKAGENAME)

cvstag:
	cvs tag version_`echo $(VERSION) | sed 's/\./_/g'`

clean:
	rm -f *.tar.gz

.PHONY: all doc dist cvstag clean
