extensions = [
    'sphinx.ext.autodoc',
    'jaraco.packaging.sphinx',
]

master_doc = "index"
html_theme = "furo"

# Link dates and other references in the changelog
extensions += ['rst.linker']
link_files = {
    '../NEWS.rst': dict(
        using=dict(GH='https://github.com'),
        replace=[
            dict(
                pattern=r'(Issue #|\B#)(?P<issue>\d+)',
                url='{package_url}/issues/{issue}',
            ),
            dict(
                pattern=r'(?m:^((?P<scm_version>v?\d+(\.\d+){1,2}))\n[-=]+\n)',
                with_scm='{text}\n{rev[timestamp]:%d %b %Y}\n',
            ),
            dict(
                pattern=r'PEP[- ](?P<pep_number>\d+)',
                url='https://peps.python.org/pep-{pep_number:0>4}/',
            ),
            dict(
                pattern=r"(Sourceforge )(?P<sf_issue>\d+)",
                url="https://sourceforge.net/p/python-irclib/bugs/{sf_issue}/",
            ),
        ],
    )
}

# Be strict about any broken references
nitpicky = True

nitpick_ignore = [
    ('py:class', 'irc.client.Base'),  # an inline superclass
    ('py:class', 'jaraco.stream.buffer.DecodingLineBuffer'),  # undocumented
]

# Include Python intersphinx mapping to prevent failures
# jaraco/skeleton#51
extensions += ['sphinx.ext.intersphinx']
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}

# Preserve authored syntax for defaults
autodoc_preserve_defaults = True


extensions += ['jaraco.tidelift']

extensions += ['sphinx.ext.viewcode']

for dependency in 'jaraco.text tempora jaraco.collections'.split():
    rtd_name = dependency.replace('.', '')
    url = f'https://{rtd_name}.readthedocs.io/en/latest'
    intersphinx_mapping.update({dependency: (url, None)})
