from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))


setup(
    name="bibcat",
    version="2.3.1",
    description="BIBCAT RDF Framework Application",
    author="KnowledgeLinks",
    author_email="knowledgelinks.io@gmail.com",
    license="MIT",
    url="http://knowledgelinks.io/#/products/bibcat",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Topic :: Database",
        "Topic :: Text Processing :: General",
        "Topic :: Text Processing :: Indexing"
    ],
    keywords="semantic web bibframe rdf",
    packages=find_packages(exclude=['tests']),
    install_requires=[
        'Flask',
        'jsonpath_ng',
        'lxml',
        'pymarc',
        'rdflib',
        'rdflib-jsonld',
        'requests',
        'fuzzywuzzy',
        'rdfframework'
        #'python-Levenshtein'
    ],
    include_package_data=True,
    package_data={
        "rdf-references": ["*.ttl"],
        "rdfw-definitions": ["*.ttl"],
        "maps": ["*.ttl"]
    }
)
