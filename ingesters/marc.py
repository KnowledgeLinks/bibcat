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
from ingesters import Ingester, new_graph 
from ingesters.sparql import *
from collections import OrderedDict

# get the current file name for logs and set logging level
MNAME = inspect.stack()[0][1]
MLOG_LVL = logging.DEBUG
logging.basicConfig(level=logging.DEBUG)

MARC2BIBFRAME = None
TRIPLESTORE_URL = "http://localhost:8080/blazegraph/sparql"


class MARCIngester(Ingester):

    def __init__(self, record):
        super(MARCIngester, self).__init__(
            rules_ttl="kds-bibcat-marc-ingestion.ttl",
            source=record)
        self.logger = logging.getLogger("%s-%s" % (MNAME, inspect.stack()[0][3]))
        self.logger.setLevel(MLOG_LVL)

    def __handle_linked_pattern__(self, **kwargs):
        pass

    def __handle_pattern__(self, **kwargs):
        pass

    def __handle_ordered__(self, **kwargs):
        pass


    def deduplicate_instances(self, identifiers=[BF.Isbn]):
        """ Takes a BIBFRAME 2.0 graph and attempts to de-duplicate 
            Instances.

        Args:
            identifiers (list): List of BIBFRAME identifiers to run 
        """
        for identifier in identifiers:
            sparql = GET_IDENTIFIERS.format(BF.Instance, identifier) 
            for row in self.graph.query(sparql):
                instance_uri, ident_value = row
                # get temp Instance URIs and 
                sparql = DEDUP_ENTITIES.format(
                    BF.identifiedBy, 
                    identifier, 
                    ident_value)
                result = requests.post(TRIPLESTORE_URL,
                    data={"query": sparql,
                      "format": "json"})
                self.logger.debug("\nquery: %s", sparql)
                if result.status_code > 399:
                    self.logger.warn("result.status_code: %s", result.status_code)
                    continue
                bindings = result.json().get('results', dict()).get('bindings', [])
                if len(bindings) < 1:
                    continue
                #! Exits out of all for loops with the first match
                existing_uri = rdflib.URIRef(
                    bindings[0].get('entity',{}).get('value'))
                replace_uris(graph, instance_uri, existing_uri, [BF.hasItem,])
                

    def deduplicate_agents(self, filter_class, agent_class):
        """Deduplicates graph"""
        lg = logging.getLogger("%s-%s" % (MNAME, inspect.stack()[0][3]))
        lg.setLevel(MLOG_LVL)
        sparql = PREFIX + """
        SELECT DISTINCT ?subject ?value
        WHERE {{
            ?subject rdf:type <{0}> .
            ?subject <{1}> ?value .
        }}""".format(agent_class, filter_class)
        for row in self.graph.query(sparql):
            agent_uri, value = row
            sparql = DEDUP_AGENTS.format(
                agent_class,
                filter_class,
                value)
            result = requests.post(TRIPLESTORE_URL,
                data={"query": sparql,
                  "format": "json"})
            if result.status_code > 399:
                lg.warn("result.status_code: %s", result.status_code)
                continue
            bindings = result.json().get('results', dict()).get('bindings', [])
            if len(bindings) < 1:
                # Agent doesn't exit in triplestore add new URI
                new_agent_uri = rdflib.URIRef("http://bibcat.org/{}".format(uuid.uuid1()))
            else:
                new_agent_uri = rdflib.URIRef(bindings[0].get("agent").get("value"))
            for subject, pred in graph.subject_predicates(object=agent_uri):
                self.graph.remove((subject, pred, agent_uri))
                self.graph.add((subject, pred, new_agent_uri))
            for pred, obj in self.graph.predicate_objects(subject=agent_uri):
                self.graph.remove((agent_uri, pred, obj))
                self.graph.add((new_agent_uri, pred, obj))
        
    

    def match_marc(self, pattern, record=None):
        """Takes a MARC21 and pattern extracted from the last element from a 
        http://marc21rdf.info/ URI

        Args:
            pattern(str): Pattern to match
            record(pymarc.Record): Optional MARC21 Record, default's to instance
        Returns:
            list of subfield values
        """
        output = []
        field_name = pattern[1:4]
        indicators = pattern[4:6]
        subfield = pattern[-1]
        if record is None:
            fields = self.source.get_fields(field_name)
        else:
            fields = record.get_fields(field_name)
        self.logger.debug("\nfield_name: %s\nindicators: %s\nsubfield:%s",
                 field_name,
                indicators,
                subfield)
             
        for field in fields:
            self.logger.debug("field: %s", field)
            if field.is_control_field():
                lg.debug("control field")
                start, end = pattern[4:].split("-")
                output.append(field.data[int(start):int(end)+1])
                continue
            indicator_key = "{}{}".format(
                field.indicators[0].replace(" ", "_"),
                field.indicators[1].replace(" ", "_"))
            self.logger.debug("indicator_key: %s", indicator_key)
            if indicator_key == indicators:
                subfields = field.get_subfields(subfield)
                self.logger.debug("subfields: %s", subfields)
                output.extend(subfields)
        self.logger.debug("\n**** output ****\n%s", output)
        return output

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
        if not i%10 and i > 0:
            lg.info(".", end="")
        if not i%100:
            lg.info(i, end="")
        total = i
    end = datetime.datetime.utcnow()
    lg.info("\nFinished %s at %s, total time=%s mins",
            total,
            end,
            (end-start).seconds / 60.0)  

def populate_entity(entity_class, graph, record):
    
    entity = rdflib.URIRef("http://bibcat.org/{}".format(uuid.uuid1()))
    graph.add((entity, rdflib.RDF.type, entity_class))
    update_linked_classes(entity_class, entity, graph, record)
    update_direct_properties(entity_class, entity, graph, record)
    update_ordered_linked_classes(entity_class, entity, graph, record)
    add_admin_metadata(entity)
    return entity

def update_direct_properties(entity_class, 
                             entity,
                             graph, 
                             record):
    """Update the graph by adding all direct literal properties of the entity 
    in the graph.

    Args:
        entity_class (url): URL of the entity's class
        entity (rdflib.URIRef): RDFlib Entity
        graph (rdflib.Graph): RDFlib Graph
        record (pymarc.Record): MARC21 Record
    """
    sparql = GET_DIRECT_PROPS.format(entity_class)
    for dest_prop, marc in MARC2BIBFRAME.query(sparql):
        for value in match_marc(record, str(marc).split("/")[-1]):
            graph.add((entity, dest_prop, rdflib.Literal(value)))

def update_linked_classes(entity_class,
                          entity, 
                          graph, 
                          record):
    """Updates RDF Graph of linked classes

    Args:
        entity_class (url): URL of the entity's class
        entity (rdflib.URIRef): RDFlib Entity
        graph (rdflib.Graph): RDFlib Graph
        record (pymarc.Record): MARC21 Record
    """
    sparql = GET_LINKED_CLASSES.format(entity_class)
    for dest_property, dest_class, prop, subj in MARC2BIBFRAME.query(sparql):
        #! Should dedup dest_class here, return found URI or BNode
        for row in MARC2BIBFRAME.query(
            GET_SRC_PROP.format(
                dest_class, 
                dest_property,
                entity_class, 
                KDS.PropertyLinker)):
            marc = row[0]
            pattern = str(marc).split("/")[-1]
            for value in match_marc(record, pattern):
                if len(value.strip()) < 1:
                    continue
                bf_class = new_existing_bnode(graph, prop, subj)
                graph.add((bf_class, rdflib.RDF.type, dest_class))
                graph.add((entity, prop, bf_class))
                graph.add((bf_class, dest_property, rdflib.Literal(value)))
                # Sets additional properties
                for pred, obj in MARC2BIBFRAME.query(
                        GET_ADDL_PROPS.format(subj)):
                    graph.add((bf_class, pred, obj))


def update_ordered_linked_classes(entity_class,
                                  entity,
                                  graph,
                                  record):
    sparql = GET_ORDERED_CLASSES.format(entity_class)
    for dest_property, dest_class, prop, subj in MARC2BIBFRAME.query(sparql):
        for row in MARC2BIBFRAME.query(
            GET_SRC_PROP.format(dest_class,
                            dest_property,
                            entity_class,
                            KDS.OrderedPropertyLinker)):
            marc = row[0]
            pattern =  str(marc).split("/")[-1]
            field_name = pattern[1:4]
            indicators = pattern[4:6]
            subfields = pattern[6:]
            fields = record.get_fields(field_name)
            for field in fields:
                bf_class = new_existing_bnode(graph, prop, subj)
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
                    # Retrieve and set additional properties 

               
            

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
    if not MARC2BIBFRAME:
        setup()
    g = new_graph()
    item = populate_entity(BF.Item, g, record)
    instance = populate_entity(BF.Instance, g, record)
    g.add((instance, BF.hasItem, item))
    g.add((item, BF.itemOf, instance))
    deduplicate_instances(g)
    deduplicate_agents(g, SCHEMA.oclc, BF.Organization) 
    add_to_triplestore(g)
    return g
                               
if __name__ == "__main__":
    if not MARC2BIBFRAME:
        setup()
    process()
