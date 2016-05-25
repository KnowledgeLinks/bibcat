"""MARC21 to BIBFRAME 2.0 command-line ingester"""
__author__ = "Jeremy Nelson, Mike Stabile"

import click
import datetime
import os
import pymarc
import rdflib
import requests

from collections import OrderedDict

BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")
KDS = rdflib.Namespace("http://knowledgelinks.io/ns/data-structures/")
RELATORS = rdflib.Namespace("http://id.loc.gov/vocabulary/relators/")

# SPARQL query templates
PREFIX  = """PREFIX bf: <{}>
PREFIX kds: <{}>
PREFIX rdf: <{}>
PREFIX rdfs: <{}>
PREFIX relators: <{}>""".format(
    BF,
    KDS,
    rdflib.RDF,
    rdflib.RDFS,
    RELATORS)

DEDUP_WORK = PREFIX + """
SELECT DISTINCT ?work
WHERE {{
    ?work bf:Title "{0}" .
    ?work relators:aut ?author .
    ?author rdfs:value "{1}"
}}"""
GET_ENTITY_MARC = PREFIX + """
SELECT ?prop ?marc
WHERE {{
    ?prop rdfs:domain <{0}> .
    ?prop kds:marc2bibframe ?marc
}}
ORDER BY ?marc"""


MARC2BIBFRAME = None
TRIPLESTORE_URL = "http://localhost:9999/blazegraph/sparql"

def deduplicate(graph):
    """Takes a BIBFRAME 2.0 graph and attempts to deduplicate any Works and
    Instances.

    Args:
        graph: RDF Graph
    """
    title, authors = None, []
    result = requests.post(TRIPLESTORE_URL,
        data={"query": DEDUP_WORK.format(title, authors),
              "format": "json"})
    if result.status_code > 399:
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
    output = []
    field_name = pattern[0:4]
    indicators = pattern[4:6]
    subfield = pattern[-1]
    fields = record.get_fields(field_name)
    for field in fields:
        indicator_key = "{}{}".format(
            field.indicators[0].replace(" ", "_"),
            field.indicators[1].replace(" ", "_"))
        if indicator_key == indicators:
            subfields = field.get_subfields(subfield)
            output.extend(subfields)
    return output

def new_graph():
    graph = rdflib.Graph()
    graph.namespace_manager.bind("bf", BF)
    graph.namespace_manager.bind("kds", KDS)
    graph.namespace_manager.bind("owl", rdflib.OWL)
    graph.namespace_manager.bind("rdf", rdflib.RDF)
    graph.namespace_manager.bind("rdfs", rdflib.RDFS)
    graph.namespace_manager.bind("relators", RELATORS)
    return graph

@click.command()
@click.argument("filepath")
def process(filepath):
    marc_reader = pymarc.MARCReader(open(filepath, "rb"), 
        to_unicode=True)
    start = datetime.datetime.utcnow()
    print("Started at {}".format(start))
    for i, record in enumerate(marc_reader):
        bf_graph = transform(record)
        deduplicate(bf_graph)
        if not i%10 and i > 0:
            print(".", end="")
        if not i%100:
            print(i, end="")
    end = datetime.datetime.utcnow()
    print("\nFinished {} at {}, total time={} mins".format(
        i,
        end,
        (end-start).seconds / 60.0))
    
   

def populate_entity(entity_class, graph, record):
    entity = rdflib.BNode()
    graph.add((entity, rdflib.RDF.type, entity_class))
    sparql = GET_ENTITY_MARC.format(entity_class)
    for prop, marc in MARC2BIBFRAME.query(sparql):
        for value in match_marc(record, str(marc).split("/")[-1]):
            g.add((work, prop, rdflib.Literal(value)))
    return entity

def setup():
    global MARC2BIBFRAME
    MARC2BIBFRAME = new_graph()
    marc2bf_filepath = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                    "rdfw-definitions",
                                    "kds-bibcat-marc-ingestion.ttl")
    MARC2BIBFRAME.parse(marc2bf_filepath, format="turtle")
 
def transform(record):
    """Function takes a MARC21 record and extracts BIBFRAME entities and 
    properties.

    Args:
        record:  MARC21 Record
    """
    # Assumes each MARC record will have at least 1 Work, Instance, and Item
    g = new_graph()
    work = populate_entity(BF.Work, g, record)
    instance = populate_entity(BF.Instance, g, record)
    g.add((work, BF.hasInstance, instance))
    g.add((instance, BF.instanceOf, work))
    item = populate_entity(BF.Item, g, record)
    g.add((instance, BF.hasItem, item))
    g.add((item, BF.itemOf, instance))
    return g
                               
if __name__ == "__main__":
    if not MARC2BIBFRAME:
        setup()
    process()
