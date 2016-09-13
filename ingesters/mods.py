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
    from ingesters.ingester import Ingester, NS_MGR, new_graph
    from ingesters.sparql import GET_ADDL_PROPS
except ImportError:
    from .ingester import Ingester, NS_MGR, new_graph
    from .sparql import GET_ADDL_PROPS

# get the current file name for logs and set logging level
MNAME = inspect.stack()[0][1]
MLOG_LVL = logging.DEBUG
logging.basicConfig(level=logging.DEBUG)

MODS2BIBFRAME = None
NS_MODS = {"mods": "{}".format(NS_MGR.mods) }

class MODSIngester(Ingester):
    """MODSIngester class extends base Ingester class"""

    def __init__(self, **kwargs):
        mods_rules = ["kds-bibcat-mods-ingestion.ttl",]
        rules = kwargs.get("rules_ttl")
        if isinstance(rules, str):
            mods_rules.append(rules)
        if isinstance(rules, list):
            mods_rules.extend(rules)
        kwargs["rules_ttl"] = mods_rules
        super(MODSIngester, self).__init__(
            **kwargs)

    def __handle_linked_bnode__(self, **kwargs):
        """Helper takes an entity with a blank nodes as a linking property
        to create children blank nodes with different classes.

        Keyword args:
            bnode(rdflib.BNode): Blank Node for Entity's property
            entity(rdflib.URIRef): Entity's URI
            destination_class(rdflib.URIRef): Destination class
            target_property(rdflib.URIRef): Target property
            target_subject((rdflib.URIRef): Target subject uri
        """
        bnode = kwargs.get("bnode")
        entity = kwargs.get("entity")
        destination_class = kwargs.get("destination_class")
        target_property = kwargs.get("target_property")
        target_subject = kwargs.get("target_subject")
        destination_property = self.rules_graph.value(
            subject=bnode,
            predicate=rdflib.RDF.type)
        xpath = self.rules_graph.value(
            subject=target_subject,
            predicate=NS_MGR.kds.srcPropXpath)
        matched_elements = self.source.findall(str(xpath), NS_MODS)
        if len(matched_elements) < 1:
            return
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
        for row in matched_elements:
            raw_value = row.text.strip()
            if len(raw_value) < 1:
                continue
            self.graph.add(
                (intermediate_bnode,
                 intermediate_bf_property,
                 rdflib.Literal(raw_value))
            )
        self.graph.add(
            (intermediate_bnode, rdflib.RDF.type, intermediate_bf_class))




    def __handle_linked_pattern__(self, **kwargs):
        """Helper takes an entity, rule, BIBFRAME class, kds:srcPropXpath
        and extracts and saves the destination property to the destination
        class.

        Keyword args:
            entity(rdflib.URIRef): Entity's URI
            rule(rdflib.Literal): XPath Literal
            destination_class(rdflib.URIRef): Destination class
            destination_property(rdflib.URIRef): Destination property
            target_property(rdflib.URIRef): Target property
            target_subject((rdflib.URIRef): Target subject uri
        """
        entity = kwargs.get("entity")
        rule = kwargs.get("rule")
        destination_class = kwargs.get("destination_class")
        destination_property = kwargs.get("destination_property")
        target_property = kwargs.get("target_property")
        target_subject = kwargs.get("target_subject")
        mods_xpath = str(rule)
        for element in self.source.findall(mods_xpath, NS_MODS):
            value = element.text
            bf_class_bnode = self.new_existing_bnode(
                target_property,
                target_subject)
            self.graph.add((bf_class_bnode, rdflib.RDF.type, destination_class))
            self.graph.add((entity, target_property, bf_class_bnode))
            if value and len(value.strip()) > 1:
                self.graph.add((bf_class_bnode,
                                destination_property,
                                rdflib.Literal(value)))
            # Sets additional properties
            for pred, obj in self.rules_graph.query(
                    GET_ADDL_PROPS.format(target_subject)):
                self.graph.add((bf_class_bnode, pred, obj))


    def __handle_pattern__(self, entity, rule, destination_property):
        """Helper takes an kds:srcPropXpath element, extracts and returns
        xpath from the element's text

        Args:
            entity(rdflib.URIRef): Entity's URI
            rule(rdflib.Literal): XPath Literal
            destination_property(rdflib.URIRef): Destination property

        Returns:
            str: Fully qualified XPath
        """
        if isinstance(destination_property, rdflib.BNode):
            for pred, obj in self.rules_graph.predicate_objects(
                    subject=destination_property):
                self.graph.add((entity, pred, obj))
            return
        mods_xpath = rule.value
        for element in self.source.findall(mods_xpath, NS_MODS):
            raw_text = element.text
            if not raw_text or len(raw_text.strip()) < 1:
                continue
            raw_text = raw_text.strip()
            #! Quick and dirty method for converting urls to URIs
            if raw_text.startswith("http"):
                object_ = rdflib.URIRef(raw_text)
            else:
                object_ = rdflib.Literal(raw_text)
            self.graph.add((entity, destination_property, object_))

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
        for obj in self.rules_graph.objects(subject=entity):
            continue


    def transform(self, mods_xml=None):
        """Overrides parent class transform and adds MODS-specific
        transformations

        Args:
            mods_xml(xml.etree.ElementTree.XML): MODS XML or None
        """
        if mods_xml is None:
            mods_xml = self.source
        super(MODSIngester, self).transform(source=mods_xml)
        self.deduplicate_agents(
            NS_MGR.schema.alternativeName,
            NS_MGR.bf.Person,
            None)
        self.deduplicate_agents(
            NS_MGR.rdfs.label,
            NS_MGR.bf.Organization,
            None)


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
