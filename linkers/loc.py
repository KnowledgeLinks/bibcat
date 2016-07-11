"""Helper Class and Functions for linking BIBFRAME 2.0 linked data with 
Library of Congress id.loc.gov linked-data webservices"""
__author__ = "Jeremy Nelson, Mike Stabile"

from .linker import Linker


class LibraryOfCongressLinker(Linker):
    """Library of Congress Linked Data Linker"""
    ID_LOC_URL = "http://id.loc.gov/"

    def __init__(self, **kwargs):
        super(LibraryOfCongressLinker, self).__init__(**kwargs)

    def run(self):
        pass
