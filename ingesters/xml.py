"""Base XML class used by specific XML ingesters like MODS and PTFS"""

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

class XMLIngester(Ingester):

    def __init__(self, **kwargs):
        self.xpath_ns = kwargs.get("xpath_ns", {})
        super(XMLIngester, self).__init__(**kwargs)

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
        matched_elements = self.source.findall(str(xpath), self.xpath_ns)
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
            raw_value = row.text
            if raw_text is None or len(raw_value.strip()) < 1:
                continue
            self.graph.add(
                (intermediate_bnode,
                 intermediate_bf_property,
                 rdflib.Literal(raw_value.strip()))
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
        for element in self.source.findall(mods_xpath, self.xpath_ns):
            value = element.text
            if not value or len(value.strip()) < 1:
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
             
    def __handle_subclasses__(self, **kwargs):
        """Helper takes an entity, rule, BIBFRAME class, kds:srcPropXpath
        and matches a value from source and then adds as either a 
        BIBFRAME Work or Instance sub class.
 
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
        bf_class_bnode = self.new_existing_bnode(
                target_property,
                target_subject)
        self.graph.add((bf_class_bnode, rdflib.RDF.type, destination_class))
        self.graph.add((entity, target_property, bf_class_bnode))
            


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
        for element in self.source.findall(mods_xpath, self.xpath_ns):
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


    def transform(self, xml=None, instance_uri=None, item_uri=None):
        """Overrides parent class transform and adds XML-specific
        transformations

        Args:
            xml(xml.etree.ElementTree.XML): XML or None
            instance_uri: URIRef for instance or None
            item_uri: URIREf for item or None
        """
        if xml is None:
            xml = self.source
        if isinstance(xml, str):
            xml = etree.XML(xml)
        super(XMLIngester, self).transform(
            source=xml,
            instance_uri=instance_uri,
            item_uri=item_uri)

