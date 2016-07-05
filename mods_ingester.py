"""MODS to BIBFRAME 2.0 command-line ingester"""
__author__ = "Jeremy Nelson, Mike Stabile"


import datetime
import click
import inspect
import logging
import pymarc
import os
import rdflib
import requests
import sys
import uuid

import xml.etree.ElementTree as etree

from collections import OrderedDict
from ingester import Ingester, new_graph 
from ingester import BF, KDS, RELATORS, PREFIX, SCHEMA
from ingester import GET_LINKED_CLASSES
sys.path.append(
    os.path.split(os.path.abspath(os.path.dirname(__file__)))[0])
try:
    from instance import config
except ImportError:
    pass

# get the current file name for logs and set logging level
MNAME = inspect.stack()[0][1]
MLOG_LVL = logging.DEBUG
logging.basicConfig(level=logging.DEBUG)

MODS = rdflib.Namespace("http://www.loc.gov/mods/v3")
MODS2BIBFRAME = None

GET_SRC_PROP = PREFIX + """
SELECT ?prop
WHERE {{
    ?subj kds:destPropXpath ?prop .
    ?subj kds:destClassUri <{0}> .
    ?subj kds:destPropUri <{1}> .
    ?subj kds:linkedClass <{2}> .
    ?subj rdf:type <{3}> .
}}"""


class MODSIngester(Ingester):
    """MODSIngester class extends base Ingester class"""

    def __init__(self, mods_xml):
        super(MODSIngester, self).__init__(
            rules_ttl="kds-bibcat-mods-ingestion.ttl",
            source=mods_xml)

    def __handle_linked_pattern__(self, **kwargs):
        """Helper takes an entity, rule, BIBFRAME class, kds:srcPropXpath 
        and extracts and saves the destination property to the destination
        class.

        Keyword args:
            entity(rdflib.URIRef): Entity's URI
            rule(rdflib.Literal): XPath Literal
            destination_class(rdflib.URIRef): Destination class
            destination_property(rdflib.URIRef): Destination property
        """
        entity = kwargs.get("entity")
        rule = kwargs.get("rule")
        destination_class = kwargs.get("destination_class")
        destination_property = kwargs.get("destination_property")
        target_property = kwargs.get("target_property")
        target_subject = kwargs.get("target_subject")
        mods_xpath = raw_xpath.replace("mods:", "{{{0}}}".format(MODS))
        for element in self.source.findall(mods_xpath):
            value = element.text
            if len(value) < 1:
                continue
            bf_class_bnode = self.new_existing_bnode(
                target_property, 
                target_subject)
            self.graph.add((bf_class_bnode, rdflib.RDF.type, destination_class))
            self.graph.add((entity, target_property, bf_class_bnode))
            self.graph.add((bf_class_bnode, 
                destination_property, 
                rdflib.Literal(value)))
            # Sets additional properties
            for pred, obj in MARC2BIBFRAME.query(
                GET_ADDL_PROPS.format(target_subject)):
                self.graph.add((bf_class_bnode, pred, obj))


    def __handle_pattern__(self, entity, rule, dest_property):
        """Helper takes an kds:srcPropXpath element, extracts and returns
        xpath from the element's text

        Args:
            entity(rdflib.URIRef): Entity's URI
            rule(rdflib.Literal): XPath Literal
            dest_property(rdflib.URIRef): Destination property

        Returns:
            str: Fully qualified XPath
        """
        raw_xpath = rule.text
        mods_xpath = raw_xpath.replace("mods:", "{{{0}}}".format(MODS)) 
        for element in self.source.findall(mods_xpath):
            self.graph.add((entity, dest_property, rdflib.Literal(element.text)))

    def __handle_ordered__(self, **kwargs):
        """Helper takes a BIBFRAME class, entity URI, destination property,
        destination class and extracts xpath values and saves to the
        ingester's graph.

        Keyword args:
            entity_class(rdflib.URIRef): BIBFRAME Class
            entity(rdflib.URIRef): Resource entity's URI
            destination_property(rdflib.URIRef): URI of destination property
            destination_class(rdflib.URIRef): URI of destination class
            target_property(rdflib.URIRef): Target property URI
            target_class(rdflib.URIRef): Target class URI
        """
        entity = kwargs.get("entity")
        entity_class = kwargs.get("entity_class")
        destination_property = kwargs.get("destination_property")
        destination_class = kwargs.get("destination_class")
        target_property = kwargs.get("target_property")
        target_subject = kwargs.get("target_subject")
            

@click.command()
@click.option("--url", default=None)
@click.option("--filepath", default=None)
def process(url, filepath):
    if not url is None:
        http_result = requests.get(url)
        if http_result.status_code > 399:
            raise ValueError("HTTP Error %s".format(http_result.status_code))
        raw_xml = http_result.text
    elif not filepath is None:
        with open(filepath) as xml_file:
            raw_xml = xml_file.read()
    mods_doc = etree.XML(raw_xml)
    bf_graph = new_graph()
    instance_uri = populate_entity(BF.Instance, bf_graph, mods_doc)
    item_uri = populate_entity(BF.Item, bf_graph, mods_doc)
    bf_graph.add((instance_uri, BF.hasItem, item_uri)) 
    return bf_graph.serialize(format='turtle').decode()
    

def setup():
    # setup log
    lg = logging.getLogger("%s-%s" % (MNAME, inspect.stack()[0][3]))
    lg.setLevel(MLOG_LVL)
    
    global MODS2BIBFRAME
    
    MODS2BIBFRAME = new_graph()
    mods2bf_filepath = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                    "rdfw-definitions",
                                    "kds-bibcat-mods-ingestion.ttl")
    lg.debug("MODS2BIBFRAME: %s\nmarc2bf_filepath: %s", 
             MODS2BIBFRAME,
             mods2bf_filepath)
    MODS2BIBFRAME.parse(mods2bf_filepath, format="turtle")

if __name__ == "__main__":
    if not MODS2BIBFRAME:
        setup()
    process()
