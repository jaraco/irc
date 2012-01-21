import os
import re

from paver.easy import *
from paver.setuputils import setup

def get_version():
	"""
	Grab the version from irclib.py.
	"""
	here = os.path.dirname(__file__)
	irclib = os.path.join(here, 'irclib.py')
	with open(irclib) as f:
		content = f.read()
	VERSION = eval(re.search('VERSION = (.*)', content).group(1))
	VERSION = '.'.join(map(str, VERSION))
	return VERSION

def read_long_description():
	f = open('README')
	try:
		data = f.read()
	finally:
		f.close()
	return data

setup(
	name="python-irclib",
	description="IRC (Internet Relay Chat) protocol client library for Python",
	long_description=read_long_description(),
	version=get_version(),
	py_modules=["irclib", "ircbot"],
	author="Joel Rosdahl",
	author_email="joel@rosdahl.net",
	maintainer="Jason R. Coombs",
	maintainer_email="jaraco@jaraco.com",
	url="http://python-irclib.sourceforge.net",
	classifiers = [
		"Development Status :: 5 - Production/Stable",
		"Intended Audience :: Developers",
		"Programming Language :: Python :: 2.3",
		"Programming Language :: Python :: 2.4",
		"Programming Language :: Python :: 2.5",
		"Programming Language :: Python :: 2.6",
		"Programming Language :: Python :: 2.7",
	],
)

@task
def generate_specfile():
	with open('python-irclib.spec.in', 'rb') as f:
		content = f.read()
	content = content.replace('%%VERSION%%', get_version())
	with open('python-irclib.spec', 'wb') as f:
		f.write(content)

@task
@needs('generate_setup', 'generate_specfile', 'minilib', 'distutils.command.sdist')
def sdist():
	"Override sdist to make sure the setup.py gets generated"
