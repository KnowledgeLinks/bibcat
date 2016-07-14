"""MODS to BIBFRAME 2.0 command-line ingester"""
__author__ = "Jeremy Nelson, Mike Stabile"


import datetime
import click
import inspect
import logging
import os
import rdflib
import requests
import sys
import uuid

import xml.etree.ElementTree as etree

from collections import OrderedDict
from ingesters.ingester import Ingester, new_graph, NS_MGR
from ingesters.sparql import *

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

MODS2BIBFRAME = None
NS_MODS = {"mods": "http://www.loc.gov/mods/v3"}

class MODSIngester(Ingester):
    """MODSIngester class extends base Ingester class"""

    def __init__(self, mods_xml=None):
        super(MODSIngester, self).__init__(
            rules_ttl="kds-bibcat-mods-ingestion.ttl",
            source=mods_xml)

    def __handle_linked_bnode__(self, **kwargs):
        """Helper takes an entity with a blank nodes as a linking property
        to create children blank nodes with different classes."""
        bnode = kwargs.get("bnode")
        entity = kwargs.get("entity")
        destination_class = kwargs.get("destination_class")
        target_property = kwargs.get("target_property")
        target_subject = kwargs.get("target_subject")
        destination_property = self.rules_graph.value(
            subject=bnode,
            predicate=rdflib.RDF.type)
        bf_class_bnode = self.new_existing_bnode(
            target_property, 
            target_subject)
        self.graph.add((bf_class_bnode, rdflib.RDF.type, destination_class))
        self.graph.add((entity, target_property, bf_class_bnode))
        intermediate_bnode = rdflib.BNode()
        self.graph.add(
            (bf_class_bnode, destination_property, intermediate_bnode))
        intermediate_bf_class = self.rules_graph.value(
            subject=bnode,
            predicate=NS_MGR.kds.destClassUri)
        intermediate_bf_property = self.rules_graph.value(
            subject=bnode,
            predicate=NS_MGR.kds.destPropUri)
        self.graph.add(
            (intermediate_bnode, rdflib.RDF.type, intermediate_bf_class))
        xpath = self.rules_graph.value(
            subject=target_subject,
            predicate=NS_MGR.kds.srcPropXpath)
        for row in self.source.findall(str(xpath), NS_MODS):
            self.graph.add(
                (intermediate_bnode,
                 intermediate_bf_property,
                 rdflib.Literal(row.text))
            )

 

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
        mods_xpath = str(rule)
        print(mods_xpath, NS_MODS)
        for element in self.source.findall(mods_xpath, NS_MODS):
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
            for pred, obj in self.rules_graph.query(
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
        mods_xpath = rule.text
        for element in self.source.findall(mods_xpath, NS):
            raw_text = element.text
            #! Quick and dirty method for converting urls to URIs
            if raw_text.startswith("http"):
                object_ = rdflib.URIRef(raw_text)
            else:
                object_ = rdflib.Literal(raw_text)
            self.graph.add((entity, dest_property, object_))

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

    def transform(self, mods_xml=None):
        """Overrides parent class transform and adds MODS-specific 
        transformations

        Args:
            mods_xml(xml.etree.ElementTree.XML): MODS XML or None
        """
        bf_instance, bf_item = super(MODSIngester, self).transform(mods_xml)
        

    
            

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
