"""Dublin Core to BIBFRAME 2.0 command-line ingester"""
__author__ = "Jeremy Nelson, Mike Stabile"

import datetime
import click
import csv
import inspect
import logging
import os
import rdflib
import requests
import sys
import uuid

import xml.etree.ElementTree as etree

from ingesters import Ingester, new_graph, NS_MGR 
from ingesters.sparql import *

import ingesters
MLOG_LVL = logging.DEBUG
logging.basicConfig(level=logging.DEBUG)

DC = rdflib.Namespace("http://purl.org/dc/elements/1.1/")
DCTERM = rdflib.Namespace("http://purl.org/dc/terms/")

class DCIngester(Ingester):

    def __init__(self, dc_xml=None):
        source = None
        if not isinstance(dc_xml, rdflib.Graph) and dc_xml:
            source = rdflib.Graph()
            source.parse(data=dc_xml, format="xml")
        super(DCIngester, self).__init__(
            rules_ttl = "kds-bibcat-dc-ingestion.ttl",
            source = source)
        #if not hasattr(self.ns, "dc"):
        #    self

    def __handle_linked_pattern__(self, **kwargs):
        """Helper takes an entity, rule, BIBFRAME class, kds:srcPropXpath 
        and extracts and saves the destination property to the destination
        class.

        Keyword args:
            entity(rdflib.URIRef): Entity's URI
            rule(rdflib.URIRef): Dublin Core URI
            destination_class(rdflib.URIRef): Destination class
            destination_property(rdflib.URIRef): Destination property
        """
        entity = kwargs.get("entity")
        rule = kwargs.get("rule")
        destination_class = kwargs.get("destination_class")
        destination_property = kwargs.get("destination_property")
        target_property = kwargs.get("target_property")
        target_subject = kwargs.get("target_subject")
        delimiter = self.rules_graph.value(
            subject=target_subject, 
            predicate=NS_MGR.kds.delimiterProp)
        for value in self.source.objects(predicate=rule):
            if len(str(value).strip()) < 1:
                continue
            
            if delimiter and isinstance(value, rdflib.Literal):
                for row in value.value.split(str(delimiter)):
                    new_object = rdflib.Literal(
                        row.strip(),
                        lang=value.language,
                        datatype=value.datatype)
                    bnode_class = self.new_existing_bnode(
                        target_property, 
                        target_subject)
                    self.graph.add(
                        (bnode_class, 
                         rdflib.RDF.type, 
                         destination_class))
                    self.graph.add(
                        (bnode_class, 
                         destination_property, 
                         new_object))
                    self.graph.add((entity, target_property, bnode_class))
                    for pred, obj in self.rules_graph.query(
                        GET_ADDL_PROPS.format(target_subject)):
                        self.graph.add((bnode_class, pred, obj))
            else:
                if isinstance(value, rdflib.Literal):
                    value = rdflib.Literal(
                        value.value.strip(), 
                        lang=value.language,
                        datatype=value.datatype)
                bnode_class = self.new_existing_bnode(
                        target_property, 
                        target_subject)
                self.graph.add(
                        (bnode_class, 
                         rdflib.RDF.type, 
                         destination_class))
                self.graph.add(
                    (bnode_class, 
                     destination_property,
                     value))
                self.graph.add((entity, target_property, bnode_class))
                for pred, obj in self.rules_graph.query(
                    GET_ADDL_PROPS.format(target_subject)):
                    self.graph.add((bnode_class, pred, obj))

        

    def transform(self, xml=None):
        """Method extracts item URI and then calls parent method
       
        Args:
            xml(string): Dublin Core XML String, default None
        """ 
        if xml:
            self.source = new_graph()
            self.source.parse(data=xml, format="xml")
        item_uri = next(self.source.subjects())
        super(DCIngester, self).transform(item_uri=item_uri)
        return item_uri

@click.command()
@click.option("--filepath", help="Full path to Dublin Core")
@click.option("--input_format", help="format should be XML or CSV", default="xml")
def handler(filepath, input_format):
    if input_format.startswith("xml"):
        iterate_xml(filepath)

def iterate_xml(filepath):
    logging.getLogger("requests").setLevel(logging.CRITICAL)
    logging.getLogger("urllib3").setLevel(logging.CRITICAL)
    ingester = DCIngester()
    count = 0
    start = datetime.datetime.utcnow()
    print("Starting DC XML at {} for records at {}".format(
        start,
        filepath))
    count = 0
    for event, elem in etree.iterparse(filepath):
        if elem.tag.endswith("Description"):
            ingester.transform(etree.tostring(elem))
            ingester.add_to_triplestore()
            if not count%10 and count > 0:
                print(".", end="")
            if not count%100:
                print(count, end="")
            count += 1
    end = datetime.datetime.utcnow()
    print("Finished DC ingestion at {} total time of {} mins for {}".format(
        end,
        (end-start).seconds / 60.0,
        count))
        
    
            
            
            
        
  
    

if __name__ == '__main__':
    iterate_xml()
