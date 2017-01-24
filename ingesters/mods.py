"""MODS to BIBFRAME 2.0 command-line ingester"""
__author__ = "Jeremy Nelson, Mike Stabile"


import click
import inspect
import logging
import os
import rdflib
import requests
import sys

import xml.etree.ElementTree as etree


sys.path.append(
    os.path.split(os.path.abspath(os.path.dirname(__file__)))[0])
try:
    from instance import config
except ImportError:
    pass
try:
    from ingesters.ingester import NS_MGR, new_graph
    from ingesters.sparql import GET_ADDL_PROPS
    from ingesters.xml import XMLIngester
except ImportError:
    from .ingester import NS_MGR, new_graph
    from .sparql import GET_ADDL_PROPS
    from .xml import XMLIngester

# get the current file name for logs and set logging level
MNAME = inspect.stack()[0][1]
MLOG_LVL = logging.DEBUG
logging.basicConfig(level=logging.DEBUG)

MODS2BIBFRAME = None
NS_MODS = {"mods": "{}".format(NS_MGR.mods) }

class MODSIngester(XMLIngester):
    """MODSIngester class extends base Ingester class"""

    def __init__(self, **kwargs):
        mods_rules = ["kds-bibcat-mods-ingestion.ttl",]
        rules = kwargs.get("rules_ttl")
        if isinstance(rules, str):
            mods_rules.append(rules)
        if isinstance(rules, list):
            mods_rules.extend(rules)
        kwargs["rules_ttl"] = mods_rules
        kwargs["xpath_ns"] = NS_MODS
        super(MODSIngester, self).__init__(
            **kwargs)


    def transform(self, xml=None, instance_uri=None, item_uri=None):
        """Overrides parent class transform and adds XML-specific
        transformations

        Args:
            xml(xml.etree.ElementTree.XML): XML or None
            instance_uri: URIRef for instance or None
            item_uri: URIREf for item or None
        """
        super(MODSIngester, self).transform(
            xml=xml,
            instance_uri=instance_uri,
            item_uri=item_uri)
        self.deduplicate_agents(
            NS_MGR.rdfs.label,
            NS_MGR.bf.Person,
            None)
        self.deduplicate_agents(
            NS_MGR.rdfs.label,
            NS_MGR.bf.Organization,
            None)

    def deduplicate_agents(self, filter_class, agent_class, calculate_uri=None):
        """Overrides default just checks for duplicates in internal BF Graph
        before calling"""
        super(MODSIngester, self).deduplicate_agents(filter_class, agent_class, None)
        agent_values = dict()
        agents = list(set([s for s in self.graph.subjects(
                                     predicate=NS_MGR.rdf.type,
                                     object=agent_class)]))
        for iri in agents:
            filter_value = self.graph.value(subject=iri, 
                                            predicate=filter_class)
            if filter_value in agent_values:
                existing_iri = agent_values.get(filter_value)
                for pred, obj in self.graph.predicate_objects(subject=iri):
                    self.graph.remove((iri, pred, obj))
                    self.graph.add((existing_iri, pred, obj))
                for subj, pred in self.graph.subject_predicates(object=iri):
                    self.graph.remove((subj, pred, iri))
                    self.graph.add((subj, pred, existing_iri))
            else:
                agent_values[filter_value] = iri
                
            
        


@click.command()
@click.option("--url", default=None)
@click.option("--filepath", default=None)
@click.option("--rules", default=[])
def process(url, filepath, rules):
    """Function takes url or filepath and an optional list of custom turtle
    rule files, creates an MODS ingester, and transforms it into BIBFRAME 2.0

    Args:
        url: Optional URL to MODS XML
        filepath: Optional filepath to MODS XML
        rules: file names of custom MODS to BIBFRAME RDF rules in turtle format
    """
    if not url is None:
        http_result = requests.get(url)
        if http_result.status_code > 399:
            raise ValueError("HTTP Error {0}".format(http_result.status_code))
        raw_xml = http_result.text
    elif not filepath is None:
        with open(filepath) as xml_file:
            raw_xml = xml_file.read()
    mods_doc = etree.XML(raw_xml)
    ingester = MODSIngester(mods_doc, custom=rules)
    ingester.transform()
    return ingester.graph.serialize(format='turtle').decode()

if __name__ == "__main__":
    process()
