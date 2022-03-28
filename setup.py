# --------------------------------------------
# Copyright 2021, Grant Viklund, Roberto Himmelbauer
# @Author: Grant Viklund, Roberto Himmelbauer
# @Date:   2021-06-01 17:00:10
# --------------------------------------------

from os import path
from setuptools import setup, find_packages

from integrations.__version__ import VERSION

readme_file = path.join(path.dirname(path.abspath(__file__)), 'README.md')

try:
    from m2r import parse_from_file
    long_description = parse_from_file(readme_file)     # Convert the file to RST for PyPI
except ImportError:
    # m2r may not be installed in user environment
    with open(readme_file) as f:
        long_description = f.read()

package_metadata = {
    'name': 'django-integrations',
    'version': VERSION,
    'description': "Tools for creating and managing multi-site integrations like API Keys and Tokens",
    'long_description': long_description,
    'url': 'https://github.com/renderbox/django-integrations/',
    'author': 'Grant Viklund, Roberto Himmelbauer',
    'author_email': 'renderbox@gmail.com',
    'license': 'MIT license',
    'classifiers': [
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    'keywords': ['django', 'app'],
}

setup(
    **package_metadata,
    packages=find_packages(),
    package_data={'integrations': ['*.html']},
    include_package_data=True,
    python_requires=">=3.6",
    install_requires=[
        'Django>=3.0, <4.1',
        'djfernet',
    ],
    extras_require={
        'dev': [
            'dj-database-url',
            'django-crispy-forms',
            'django-allauth',
            'django-extensions',
            'psycopg2-binary',
        ],
        'test': [],                         # Packages needed to run tests
        'prod': [],                         # Packages needed to run in the deployment
        'build': [                          # Packages needed to build the package
            'setuptools',
            'wheel',
            'twine',
            'm2r',
        ],
        'docs': [                           # Packages needed to generate docs
            'recommonmark',
            'm2r',
            'django_extensions',
            'coverage',
            'Sphinx',
            'rstcheck',
            'sphinx-rtd-theme',  # Assumes a Read The Docs theme for opensource projects
        ],
    }
)