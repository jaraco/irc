import paver.easy
import paver.setuputils

def read_long_description():
    with open('README') as f:
        data = f.read()
    return data

paver.setuputils.setup(
    name="python-irclib",
    description="IRC (Internet Relay Chat) protocol client library for Python",
    long_description=read_long_description(),
    use_hg_version=True,
    py_modules=["irclib", "ircbot"],
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
@paver.easy.needs('generate_setup', 'minilib', 'distutils.command.sdist')
def sdist():
    "Override sdist to make sure the setup.py gets generated"
