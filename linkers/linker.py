"""Helper module for linking existing BIBFRAME resources to external data
sources like Library of Congress, DBPedia, VIAF, and others."""

__author__ = "Jeremy Nelson, Mike Stabile"

import rdflib
import sys


from ingesters.ingester import new_graph, PROJECT_BASE
sys.path.append(PROJECT_BASE)
try:
    import rdfw as rdfframework
except ImportError:
    pass
from rdfframework.utilities import RdfNsManager

NS = RdfNsManager()
NS.bind("dbo", rdflib.Namespace("http://dbpedia.org/ontology/"))
NS.bind("dbp", rdflib.Namespace("http://dbpedia.org/property/"))
NS.bind("dbr", rdflib.Namespace("http://dbpedia.org/resource/"))

def create_graph():
    graph = new_graph(namespace_manager=NS)
    return graph

class Linker(object):
    """Base Linker class for all other linker classes"""
    ns = NS
    def __init__(self, **kwargs):
        pass

    def run(self):
        pass


