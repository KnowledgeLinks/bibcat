"""Helper module for linking existing BIBFRAME resources to external data 
sources like Library of Congress, DBPedia, VIAF, and others."""

__author__ = "Jeremy Nelson, Mike Stabile"

class Linker(object):

    def __init__(self, **kwargs):
        pass

    def run(self):
        pass

class CarrierLinker(Linker):

    def __init__(self, **kwargs):
        pass

class DBPediaLinker(Linker):
    SPARQL_ENDPOINT = "http://dbpedia.org/sparql"

    def __init__(self, **kwargs):
        pass

class LibraryOfCongressLinker(Linker):
    ID_LOC_URL = "http://id.loc.gov/"

    def __init__(self, **kwargs):
        pass


