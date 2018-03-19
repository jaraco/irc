#!/usr/bin/env python

# Project skeleton maintained at https://github.com/jaraco/skeleton

import io

import setuptools

with io.open('README.rst', encoding='utf-8') as readme:
    long_description = readme.read()

name = 'irc'
description = 'IRC (Internet Relay Chat) protocol library for Python'
nspkg_technique = 'native'
"""
Does this package use "native" namespace packages or
pkg_resources "managed" namespace packages?
"""

params = dict(
    name=name,
    use_scm_version=True,
    author="Joel Rosdahl",
    author_email="joel@rosdahl.net",
    maintainer="Jason R. Coombs",
    maintainer_email="jaraco@jaraco.com",
    description=description or name,
    long_description=long_description,
    url="https://github.com/jaraco/" + name,
    packages=setuptools.find_packages(),
    include_package_data=True,
    namespace_packages=(
        name.split('.')[:-1] if nspkg_technique == 'managed'
        else []
    ),
    python_requires='>=2.7,!=3.0.*,!=3.1.*,!=3.2.*',
    install_requires=[
        'six',
        'jaraco.collections',
        'jaraco.text',
        'jaraco.itertools>=1.8',
        'jaraco.logging',
        'jaraco.functools>=1.5',
        'jaraco.stream',
        'pytz',
        'more_itertools',
        'tempora>=1.6',
    ],
    extras_require={
        'testing': [
            # upstream
            'pytest>=2.8',
            'pytest-sugar',
            'collective.checkdocs',
            'pytest-flake8',

            # local
            'backports.unittest_mock',
            'pygments',
        ],
        'docs': [
            # upstream
            'sphinx',
            'jaraco.packaging>=3.2',
            'rst.linker>=1.9',

            # local
        ],
    },
    setup_requires=[
        'setuptools_scm>=1.15.0',
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
    ],
    entry_points={
    },
)
if __name__ == '__main__':
    setuptools.setup(**params)
