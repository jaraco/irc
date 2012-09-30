import os
import platform

import setuptools

import paver.easy
import paver.setuputils

def read_long_description():
    with open('README') as f:
        data = f.read()
    return data

paver.setuputils.setup(
    name="irc",
    description="IRC (Internet Relay Chat) protocol client library for Python",
    long_description=read_long_description(),
    use_hg_version=True,
    packages=setuptools.find_packages(),
    author="Joel Rosdahl",
    author_email="joel@rosdahl.net",
    maintainer="Jason R. Coombs",
    maintainer_email="jaraco@jaraco.com",
    url="http://python-irclib.sourceforge.net",
    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
    ],
    setup_requires=[
        'hgtools',
    ],
)

@paver.easy.task
def upload_project_web():
    """
    Generate the project web page at sourceforge using the reStructuredText
    README.
    """
    import docutils.core
    docutils.core.publish_file(source_path='README',
        destination_path='readme.html', writer_name='html')
    cmd = 'pscp' if platform.system() == 'Windows' else 'scp'
    paver.easy.sh('{cmd} readme.html web.sourceforge.net:'
        '/home/project-web/python-irclib/htdocs/index.html'
        .format(cmd=cmd))
    os.remove('readme.html')

@paver.easy.task
@paver.easy.needs('generate_setup', 'minilib', 'distutils.command.sdist')
def sdist():
    "Override sdist to make sure the setup.py gets generated"

def upload_sf():
    # this is the technique used to upload the dist to sourceforge
    raise NotImplementedError('code is not functional - just here for '
        'reference')
    scp = 'pscp' if platform.system() == 'Windows' else 'scp'
    sf_dest = 'frs.sourceforge.net:/home/frs/project/python-irclib'
    cmd = '{scp} dist/{name} {sf_dest}'
