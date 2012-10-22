import sys

import setuptools

def read_long_description():
    with open('README') as f:
        data = f.read()
    return data

importlib_req = ['importlib'] if sys.version_info < (2,7) else []

setup_params = dict(
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
        "Programming Language :: Python :: 3",
    ],
    install_requires=[
    ] + importlib_req,
    setup_requires=[
        'hgtools',
        'pytest-runner',
    ],
    tests_require=[
        'pytest',
    ],
    use_2to3=True,
    use_2to3_exclude_fixers=[
        'lib2to3.fixes.fix_import',
        'lib2to3.fixes.fix_next',
        'lib2to3.fixes.fix_print',
    ],
)

if __name__ == '__main__':
    setuptools.setup(**setup_params)
