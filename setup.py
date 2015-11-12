__author__ = "Jeremy Nelson"
__license__ = "GPLv3"
__version_info__ = ('0', '1', '0')
__version__ = '.'.join(__version_info__)

from setuptools import find_packages, setup

setup(
    name='IslandoraOpenBadges',
    version= __version__,
    author=__author__,
    author_email='jermnelson@gmail.com',
    description="Islandora REST API for issuing OpenBadges",
    long_description="",
    packages=find_packages(),
    include_package_data=True,
    platforms='any',
    install_requires=[
        'falcon',
        'rdflib',
        'requests'
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
