VERSION := `sed -n -e '/VERSION = /{s/VERSION = \(.*\), \(.*\), \(.*\)/\1.\2.\3/;p;}' <irclib.py`

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
    python-irclib.spec \
    servermap \
    setup.py \
    testbot.py

PACKAGENAME = python-irclib-$(VERSION)

all: $(DISTFILES)

setup.py: setup.py.in
	sed 's/%%VERSION%%/'$(VERSION)'/g' setup.py.in >setup.py

python-irclib.spec: python-irclib.spec.in
	sed 's/%%VERSION%%/'$(VERSION)'/g' python-irclib.spec.in >python-irclib.spec

dist: $(DISTFILES)
	mkdir $(PACKAGENAME)
	cp -r $(DISTFILES) $(PACKAGENAME)
	tar cvzf $(PACKAGENAME).tar.gz $(PACKAGENAME)
	zip -r9yq $(PACKAGENAME).zip $(PACKAGENAME)
	rm -rf $(PACKAGENAME)

cvstag:
	ver=$(VERSION); echo cvs tag version_`echo $$ver | sed 's/\./_/g'`

clean:
	rm -rf *~ *.pyc build python-irclib.spec setup.py

.PHONY: all doc dist cvstag clean
