import setuptools

def read_long_description():
    with open('README.rst') as f:
        data = f.read()
    with open('CHANGES.rst') as f:
        data += '\n\n' + f.read()
    return data

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
        "Programming Language :: Python :: 3",
    ],
    install_requires=[
        'six',
        'jaraco.util',
    ],
    setup_requires=[
        'hgtools>=5',
        'pytest-runner',
    ],
    tests_require=[
        'pytest',
        'mock',
    ],
)

if __name__ == '__main__':
    setuptools.setup(**setup_params)
