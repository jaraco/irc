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
	VERSION = "'%s'" % '.'.join(map(str, VERSION))
	return VERSION

setup(
	name="python-irclib",
	version=get_version(),
	py_modules=["irclib", "ircbot"],
	author="Joel Rosdahl",
	author_email="joel@rosdahl.net",
	url="http://python-irclib.sourceforge.net",
)

@task
@needs('generate_setup', 'minilib', 'distutils.command.sdist')
def sdist():
	"Override sdist to make sure the setup.py gets generated"
