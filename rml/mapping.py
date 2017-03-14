"""mapping.py - RDF Mapping Language Base Class contains TriplesMaps to
compare with mapping of source data to output RDF"""
__author __ "Jeremy Nelson, Mike Stabile"

import rdflib
from models import TripleMap

class RMLMapping(object):

    def __init__(self, triples_maps):
        self.triples_maps = triples_maps
