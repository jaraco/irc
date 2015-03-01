import io
import sys

import setuptools

def read_long_description():
    with io.open('README.rst', encoding='utf-8') as f:
        data = f.read()
    return data

needs_pytest = {'pytest', 'test', 'ptr', 'release'}.intersection(sys.argv)
pytest_runner = ['pytest_runner'] if needs_pytest else []
needs_sphinx = {'build_sphinx', 'upload_docs', 'release'}.intersection(sys.argv)
sphinx = ['sphinx', 'pytest'] if needs_sphinx else []

setup_params = dict(
    name="irc",
    description="IRC (Internet Relay Chat) protocol client library for Python",
    long_description=read_long_description(),
    use_vcs_version=True,
    packages=setuptools.find_packages(),
    author="Joel Rosdahl",
    author_email="joel@rosdahl.net",
    maintainer="Jason R. Coombs",
    maintainer_email="jaraco@jaraco.com",
    url="http://python-irclib.sourceforge.net",
    license="MIT",
    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
    ],
    install_requires=[
        'six',
        'jaraco.collections',
        'jaraco.text',
        'jaraco.itertools',
        'jaraco.logging',
    ],
    setup_requires=[
        'hgtools>=5',
    ] + pytest_runner + sphinx,
    tests_require=[
        'pytest',
        'mock',
    ],
)

if __name__ == '__main__':
    setuptools.setup(**setup_params)
