#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import setuptools_scm

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
]

# General information about the project.
project = 'irc'
copyright = '2014-2015 Jason R. Coombs'

# The short X.Y version.
version = setuptools_scm.get_version(root='..')
# The full version, including alpha/beta/rc tags.
release = version

master_doc = 'index'
