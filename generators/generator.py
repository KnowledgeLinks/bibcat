"""BIBFRAME 2.0 Generator"""
import logging
import os
import rdflib
import sys
import uuid
__author__ = "Jeremy Nelson, Mike Stabile"

BIBCAT_BASE = os.path.abspath(
    os.path.split(
        os.path.dirname(__file__))[0])
PROJECT_BASE = os.path.split(BIBCAT_BASE)[0]
sys.path.append(PROJECT_BASE)
try:
    from instance import config
    import rdfw as rdfframework
    from rdfframework.utilities import RdfNsManager
    RdfNsManager.log_level = logging.CRITICAL
except ImportError:
    logging.error("Error importing {}".format(PROJECT_BASE))
try:
    version_path = os.path.join(
        BIBCAT_BASE,
        "VERSION")
    with open(version_path) as version:
        __version__ = version.read().strip()
except:
    __version__ = "unknown"

NS_MGR = RdfNsManager()
NS_MGR.bind("bf", "http://id.loc.gov/ontologies/bibframe/")
NS_MGR.bind("kds", "http://knowledgelinks.io/ns/data-structures/")
NS_MGR.bind("schema", "http://schema.org/")
NS_MGR.bind("owl", rdflib.OWL)
NS_MGR.bind("relators", "http://id.loc.gov/vocabulary/relators/")

class Generator(object):
    """Base class for all BIBFRAME generators"""

    def __init__(self, **kwargs):
        """Creates defaults for all generators"""
        self.triplestore_url = kwargs.get(
            "url",
            "http://localhost:9999/blazegraph/sparql")
        self.base_url = kwargs.get("base_url")
        if self.base_url is None:
            if hasattr(config, "BASE_URL"):
                self.base_url = config.BASE_URL
            else:
                self.base_url = "http://bibcat.org/"

    def __generate_uri__(self):
        """Method generates an URI based on the base_url"""
        uid = uuid.uuid1()
        if self.base_url.endswith("/"):
            pattern = "{0}{1}"
        else:
            pattern = "{0}/{1}"
        return rdflib.URIRef(pattern.format(self.base_url, uid))

    def report(self, start, end):
        """Runs a report on the generator, should be overridden by children
        classes"""
        pass

    def run(self):
        """Runs generator on triplestore, method should be overridden by
        children classes"""
        pass

def new_graph():
    """Function creates a new graph with RDF Framework namespace
    Manager"""
    graph = rdflib.Graph(namespace_manager=NS_MGR)
    return graph
