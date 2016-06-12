"""MARC21 to BIBFRAME 2.0 command-line ingester"""
__author__ = "Jeremy Nelson, Mike Stabile"

import os
import datetime
import logging
import inspect
import pymarc
import rdflib
import requests
import click
import uuid

from collections import OrderedDict
# get the current file name for logs and set logging level
MNAME = inspect.stack()[0][1]
MLOG_LVL = logging.DEBUG
logging.basicConfig(level=logging.DEBUG)

BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")
KDS = rdflib.Namespace("http://knowledgelinks.io/ns/data-structures/")
RELATORS = rdflib.Namespace("http://id.loc.gov/vocabulary/relators/")
SCHEMA = rdflib.Namespace("http://www.schema.org/")

BIBCAT_URL = "http://bibcat.org/"

# SPARQL query templates
PREFIX  = """PREFIX bf: <{}>
PREFIX kds: <{}>
PREFIX rdf: <{}>
PREFIX rdfs: <{}>
PREFIX bc: <http://knowledgelinks.io/ns/bibcat/> 
PREFIX m21: <http://knowledgelinks.io/ns/marc21/> 
PREFIX relators: <{}>
PREFIX schema: <{}>""".format(
    BF,
    KDS,
    rdflib.RDF,
    rdflib.RDFS,
    RELATORS,
    SCHEMA)

#GET_ENTITY_MARC = PREFIX + """
#SELECT ?prop ?marc
#WHERE {{
#    ?prop rdfs:domain <{0}> .
#    ?prop kds:marc2bibframe ?marc
#}}
#ORDER BY ?marc"""


GET_LINKED_CLASSES = PREFIX + """
SELECT ?dest_prop ?dest_class ?linked_range
WHERE {{
   ?subj kds:destClassUri ?dest_class .
   ?subj kds:destPropUri ?dest_prop .
   ?subj kds:linkedRange ?linked_range .
   ?subj kds:linkedClass <{0}> .
   ?subj rdf:type kds:PropertyLinker .
}}"""

GET_ORDERED_CLASSES = PREFIX + """
SELECT ?dest_prop ?dest_class ?linked_range
WHERE {{
   ?subj kds:destClassUri ?dest_class .
   ?subj kds:destPropUri ?dest_prop .
   ?subj kds:linkedRange ?linked_range .
   ?subj kds:linkedClass <{0}> .
   ?subj rdf:type kds:OrderedPropertyLinker .
}}"""


GET_DIRECT_PROPS = PREFIX + """
SELECT ?dest_prop ?marc
WHERE {{
    ?subj kds:destClassUri <{0}> .
    ?subj kds:destPropUri ?dest_prop .
    ?subj kds:srcPropUri ?marc .
}}"""


GET_ORDERED_MARC_LIST = PREFIX + """
SELECT ?marc
WHERE {{
    ?subj kds:srcOrderedPropUri/rdf:rest*/rdf:first ?marc .
    ?subj kds:destClassUri <{0}> .
}}"""

GET_MARC = PREFIX + """
SELECT ?marc
WHERE {{
    ?subj kds:srcPropUri ?marc .
    ?subj kds:destClassUri <{0}> .
    ?subj kds:linkedClass <{1}> .
}}"""



MARC2BIBFRAME = None
TRIPLESTORE_URL = "http://localhost:9999/blazegraph/sparql"

def deduplicate(graph):
    """ Takes a BIBFRAME 2.0 graph and attempts to deduplicate any Works and
        Instances.

        :arg graph: RDF Graph
    """
    # setup log
    lg = logging.getLogger("%s-%s" % (MNAME, inspect.stack()[0][3]))
    lg.setLevel(MLOG_LVL)
    
    title, authors = None, []
    result = requests.post(TRIPLESTORE_URL,
        data={"query": DEDUP_WORK.format(title, authors),
              "format": "json"})
    lg.debug("\nquery: %s", DEDUP_WORK.format(title, authors))
    if result.status_code > 399:
        lg.warn("result.status_code: %s", result.status_code)
        return

def match_marc(record, pattern):
    """Takes a MARC21 and pattern extracted from the last element from a 
    http://marc21rdf.info/ URI

    Args:
        record:  MARC21 Record
        pattern: Pattern to match
    Returns:
        list of subfield values
    """
    
    # setup log
    lg = logging.getLogger("%s-%s" % (MNAME, inspect.stack()[0][3]))
    lg.setLevel(MLOG_LVL)
    
    output = []
    field_name = pattern[1:4]
    indicators = pattern[4:6]
    subfield = pattern[-1]
    fields = record.get_fields(field_name)
    
    lg.debug("\nfield_name: %s\nindicators: %s\nsubfield:%s",
             field_name,
             indicators,
             subfield)
             
    for field in fields:
        lg.debug("field: %s", field)
        if field.is_control_field():
            lg.debug("control field")
            start, end = pattern[4:].split("-")
            output.append(field.data[int(start):int(end)+1])
            continue
        indicator_key = "{}{}".format(
            field.indicators[0].replace(" ", "_"),
            field.indicators[1].replace(" ", "_"))
        lg.debug("indicator_key: %s", indicator_key)
        if indicator_key == indicators:
            subfields = field.get_subfields(subfield)
            lg.debug("subfields: %s", subfields)
            output.extend(subfields)
    lg.debug("\n**** output ****\n%s", output)
    return output

def new_graph():
    # setup log
    lg = logging.getLogger("%s-%s" % (MNAME, inspect.stack()[0][3]))
    lg.setLevel(MLOG_LVL)
    
    graph = rdflib.Graph()
    graph.namespace_manager.bind("bf", BF)
    graph.namespace_manager.bind("kds", KDS)
    graph.namespace_manager.bind("owl", rdflib.OWL)
    graph.namespace_manager.bind("rdf", rdflib.RDF)
    graph.namespace_manager.bind("rdfs", rdflib.RDFS)
    graph.namespace_manager.bind("relators", RELATORS)
    graph.namespace_manager.bind("schema", SCHEMA)
    return graph

@click.command()
@click.argument("filepath")
def process(filepath):
    # setup log
    lg = logging.getLogger("%s-%s" % (MNAME, inspect.stack()[0][3]))
    lg.setLevel(MLOG_LVL)
    
    lg.debug("filepath: %s", filepath)
    marc_reader = pymarc.MARCReader(open(filepath, "rb"), 
        to_unicode=True)
    start = datetime.datetime.utcnow()
    total = 0
    lg.info("Started at %s", start)
    for i, record in enumerate(marc_reader):
        bf_graph = transform(record)
        #deduplicate(bf_graph)
        if not i%10 and i > 0:
            lg.debug(".", end="")
        if not i%100:
            lg.debug(i, end="")
        total = i
    end = datetime.datetime.utcnow()
    lg.info("\nFinished %s at %s, total time=%s mins",
            total,
            end,
            (end-start).seconds / 60.0)  

def populate_entity(entity_class, graph, record):
    # setup log
    lg = logging.getLogger("%s-%s" % (MNAME, inspect.stack()[0][3]))
    lg.setLevel(MLOG_LVL)
    
    entity = rdflib.URIRef("http://bibcat.org/{}".format(uuid.uuid1()))
    graph.add((entity, rdflib.RDF.type, entity_class))
    update_linked_classes(entity_class, entity, graph, record)
    update_direct_properties(entity_class, entity, graph, record)
    update_ordered_linked_classes(entity_class, entity, graph, record)
    return entity

def update_direct_properties(entity_class, 
                             entity,
                             graph, 
                             record):
    sparql = GET_DIRECT_PROPS.format(entity_class)
    for dest_prop, marc in MARC2BIBFRAME.query(sparql):
        for value in match_marc(record, str(marc).split("/")[-1]):
            graph.add((entity, dest_prop, rdflib.Literal(value)))

def update_linked_classes(entity_class,
                          entity, 
                          graph, 
                          record):
    sparql = GET_LINKED_CLASSES.format(entity_class)
    for dest_property, dest_class, prop in MARC2BIBFRAME.query(sparql):
        #! Should dedup dest_class here, return found URI or BNode
        for row in MARC2BIBFRAME.query(
            GET_MARC.format(dest_class, entity_class)):
            marc = row[0]
            pattern = str(marc).split("/")[-1]
            for value in match_marc(record, pattern):
                if len(value.strip()) < 1:
                    continue
                bf_class = rdflib.BNode()
                graph.add((bf_class, rdflib.RDF.type, dest_class))
                graph.add((entity, prop, bf_class))
                graph.add((bf_class, dest_property, rdflib.Literal(value)))

def update_ordered_linked_classes(entity_class,
                                  entity,
                                  graph,
                                  record):
    sparql = GET_ORDERED_CLASSES.format(entity_class)
    for dest_property, dest_class, prop in MARC2BIBFRAME.query(sparql):
        for row in MARC2BIBFRAME.query(
            GET_MARC.format(dest_class, 
                            entity_class)):
            marc = row[0]
            pattern =  str(marc).split("/")[-1]
            field_name = pattern[1:4]
            indicators = pattern[4:6]
            subfields = pattern[6:]
            fields = record.get_fields(field_name)
            for field in fields:
                bf_class = rdflib.BNode()
                indicator_key = "{}{}".format(
                    field.indicators[0].replace(" ", "_"),
                    field.indicators[1].replace(" ", "_"))
                if indicator_key != indicators:
                    continue
                ordered_value = ''
                for subfield in subfields:
                    ordered_value += ' '.join(
                        field.get_subfields(subfield)) + " "
                if len(ordered_value) > 0:
                    graph.add(
                        (bf_class, dest_property, rdflib.Literal(ordered_value.strip())))
                    graph.add((bf_class, rdflib.RDF.type, dest_class))
                    graph.add((entity, prop, bf_class))


               
            

def setup():
    # setup log
    lg = logging.getLogger("%s-%s" % (MNAME, inspect.stack()[0][3]))
    lg.setLevel(MLOG_LVL)
    
    global MARC2BIBFRAME
    
    MARC2BIBFRAME = new_graph()
    marc2bf_filepath = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                    "rdfw-definitions",
                                    "kds-bibcat-marc-ingestion.ttl")
    lg.debug("MARC2BIBFRAME: %s\nmarc2bf_filepath: %s", 
             MARC2BIBFRAME,
             marc2bf_filepath)
    MARC2BIBFRAME.parse(marc2bf_filepath, format="turtle")
 
def transform(record):
    """Function takes a MARC21 record and extracts BIBFRAME entities and 
    properties.

    Args:
        record:  MARC21 Record
    """
    # Assumes each MARC record will have at least 1 Work, Instance, and Item
    
    # setup log
    lg = logging.getLogger("%s-%s" % (MNAME, inspect.stack()[0][3]))
    lg.setLevel(MLOG_LVL)
    
    lg.debug("*** record ***\n&s", record)
    g = new_graph()
    item = populate_entity(BF.Item, g, record)
    instance = populate_entity(BF.Instance, g, record)
    g.add((instance, BF.hasItem, item))
    g.add((item, BF.itemOf, instance))
    return g
                               
if __name__ == "__main__":
    if not MARC2BIBFRAME:
        setup()
    process()
