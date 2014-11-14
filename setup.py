__author__ = "Jeremy Nelson"
__license__ = "GPLv3"
__version_info__ = ('0', '0', '1')
__version__ = '.'.join(__version_info__)

from setuptools import find_packages, setup

setup(
    name: 'IslandoraOpenBadges',
    version: __version__,
    author=__author__,
    author_email='jermnelson@gmail.com',
    description="Islandora Flask application for issuing OpenBadges",
    long_description=,
    packages=find_packages(),
    include_package_data=True,
    platforms='any',
    install_requires=[
        'Flask',
        'rdflib',
        'Flask-Negotiate',
        'Flask-FedoraCommons'
    ],
    classifiers=[
        'Framework :: Flask',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.4',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application'
    ]
)
