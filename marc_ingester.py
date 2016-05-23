"""MARC21 to BIBFRAME 2.0 command-line ingester"""
__author__ = "Jeremy Nelson, Mike Stabile"

import click
import pymarc
import rdflib
import requests

from collections import OrderedDict

BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")
KDS = rdflib.Namespace("http://knowledgelinks.io/ns/data-structures/")
RELATORS = rdflib.Namespace("http://id.loc.gov/vocabulary/relators/")

def new_entity():
    graph = rdflib.Graph()
    graph.namespace_manager.bind("bf", BF)
    graph.namespace_manager.bind("kds", KDS)
    graph.namespace_manager.bind("relators", RELATORS)
    return graph

def match_marc(record, pattern):
    """Takes a MARC21 and pattern extracted from the last element from a 
    http://marc21rdf.info/ URI

    Args:
        record:  MARC21 Record
        pattern: Pattern to match
    Returns:
        list of subfield values
    """
    field = record[pattern[1:4]]
    if field is not None:
        if field.indicators == [pattern[4], pattern[5]]:
            return field.get_subfields(pattern[6])
        if field.indicators[0] == pattern[4] or pattern[4] == '_':
            if field.indicators[1] == pattern[5] or \
               pattern[5] == "_":
                return field.get_subfields(pattern[6])

def setup():
    global MARC2BIBFRAME
    MARC2BIBFRAME = dict()
    for subject, marc in bibcat_marc_ingestion.subject_objects(
        object=KDS.marc2bibframe):
        pattern = marc.split("/")[-1]
        field = pattern[1:4]
        indicators = pattern[4:6]
        subfield = pattern[-1]
        if field in MARC2BIBFRAME:
            if indicators in MARC2BIBFRAME[field]:
                if subfield in MARC2BIBFRAME[field][indicators]:
                    MARC2BIBFRAME[field][indicators][subfield].append(subject)
                else:
                    MARC2BIBFRAME[field][indicators][subfield] = [subject,]
            else:
		MARC2BIBFRAME[field][indicators] = dict() 
		MARC2BIBFRAME[field][indicators][subfield] = [subject,]
        else:
            MARC2BIBFRAME[field] = dict()
            MARC2BIBFRAME[field][indicators] = dict()
            MARC2BIBFRAME[field][indicators][subfield] = [subject,]

def transform(record):
    """Function takes a MARC21 record and extracts BIBFRAME entities and 
    properties.

    Args:
        record:  MARC21 Record
    """
    # Assumes each MARC record will have at least 1 Work, Instance, and Item
    g = new_entity()
    work = rdflib.BNode()
    instance = rdflib.BNode()
    g.add((work, BF.hasInstance, instance))
    g.add((instance, BF.instanceOf, work))
    item = rdflib.BNode()
    g.add((instance, BF.hasItem, item))
    g.add((item, BF.itemOf, instance))
    for field_name in sorted(MARC2BIBFRAME):
        if record[field_name]:
            rule = MARC2BIBFRAME[field_name]
            fields = record.get_fields(field_name)
            for field in fields:
                indicator_key = "{}{}".format(
                    field.indicators[0].replace(" ", "_"),
                    field.indicators[1].replace(" ", "_"))
                if indicator_key in rule:
                    subfields = rule[indicator_key].keys()
                    for subfield in subfields:
                        if subfield in field:
                            print(field[subfield], rule[indicator_key][subfield])
                    
            
                
                
              


if __name__ == "__main__":
    print("In MARC21 to BIBFRAME 2.0")
