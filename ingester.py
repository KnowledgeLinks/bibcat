"""BIBFRAME 2.0 ingester helper functions"""
__author__ = "Jeremy Nelson, Mike Stabile"

import datetime
import inspect
import logging
import os
import rdflib
import sys
import uuid

# get the current file name for logs and set logging level
MNAME = inspect.stack()[0][1]
MLOG_LVL = logging.DEBUG
logging.basicConfig(level=logging.DEBUG)

sys.path.append(
    os.path.split(os.path.abspath(os.curdir))[0])
try:
    from instance import config
except ImportError:
    pass

BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")
KDS = rdflib.Namespace("http://knowledgelinks.io/ns/data-structures/")
RELATORS = rdflib.Namespace("http://id.loc.gov/vocabulary/relators/")
SCHEMA = rdflib.Namespace("http://schema.org/")

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

GET_BLANK_NODE = PREFIX + """
SELECT ?subject 
WHERE {{
    ?instance <{0}> ?subject .
}}"""

GET_DIRECT_PROPS = PREFIX + """
SELECT ?dest_prop ?src_prop
WHERE {{
    ?subj kds:destClassUri <{0}> .
    ?subj kds:destPropUri ?dest_prop .
    ?subj kds:srcPropUri ?src_prop .
}}"""

GET_LINKED_CLASSES = PREFIX + """
SELECT ?dest_prop ?dest_class ?linked_range ?subj
WHERE {{
   ?subj kds:destClassUri ?dest_class .
   ?subj kds:destPropUri ?dest_prop .
   ?subj kds:linkedRange ?linked_range .
   ?subj kds:linkedClass <{0}> .
   ?subj rdf:type kds:PropertyLinker .
}}"""


GET_ORDERED_CLASSES = PREFIX + """
SELECT ?dest_prop ?dest_class ?linked_range ?subj
WHERE {{
   ?subj kds:destClassUri ?dest_class .
   ?subj kds:destPropUri ?dest_prop .
   ?subj kds:linkedRange ?linked_range .
   ?subj kds:linkedClass <{0}> .
   ?subj rdf:type kds:OrderedPropertyLinker .
}}"""

GET_SRC_PROP = PREFIX + """
SELECT ?prop
WHERE {{
    ?subj kds:destPropUri ?prop .
    ?subj kds:destClassUri <{0}> .
    ?subj kds:destPropUri <{1}> .
    ?subj kds:linkedClass <{2}> .
    ?subj rdf:type <{3}> .
}}"""


class Ingester(object):
    """Base class for transforming various metadata format/vocabularies to 
    BIBFRAME RDF Linked Data"""

    def __init__(self, **kwargs):
        self.base_url = kwargs.get("base_url", "http://bibcat.org/")
        if "graph" in kwargs:
            self.graph = kwargs.get("graph")
        else:
            self.graph = new_graph()
        if not "rules_ttl" in kwargs:
            raise ValueError("Ingester Requires Rules Turtle file name")
        rules_filepath = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
                "rdfw-definitions",
                kwargs.get("rules_ttl"))
        self.rules_graph = new_graph()
        self.rules_graph.parse(rules_filepath, format='turtle')
        self.source = kwargs.get("source")
        self.triplestore_url = kwargs.get(
            "triplestore_url", 
            "http://localhost:8080/blazegraph/sparql")

    def add_admin_metadata(self, entity):
        """Takes a graph and adds the AdminMetadata for the entity

        Args:
            entity (rdflib.URIRef): URI of the entity
        """
        generation_process = rdflib.BNode()
        self.graph.add((generation_process, rdflib.RDF.type, BF.GenerationProcess))
        self.graph.add((generation_process, 
            BF.generationDate, 
            rdflib.Literal(datetime.datetime.utcnow().isoformat())))
        self.graph.add((generation_process,
            rdflib.RDF.value,
            rdflib.Literal("Generated by RDF Framework from KnowledgeLinks.io", 
                   lang="en")))
        self.graph.add((entity, BF.generationProcess, generation_process))


    def add_to_triplestore(self, graph):
       """Takes graph and sends POST to add to triplestore

       Args:
           graph(rdflib.Graph): Transformed and deduplicated RDF BIBFRAME Graph
       """
       add_result = requests.post(self.triplestore_url,
           data=self.graph.serialize(format='turtle'),
           headers={"Content-Type": "text/turtle"})
       if add_result.status_code > 399:
           lg.error("Could not add graph to {}, status={}".format(
               self.triplestore_url,
               add_result.status_code))


    def new_existing_bnode(self, bf_property, rule):
       """Returns existing blank node or a new if it doesn't exist

       Args:
           bf_property (str): RDF property URI
           rule (rdflib.URIRef): RDF subject of the map rule

       Returns:
           rdflib.BNode: Existing or New blank node
       """
       blank_node = None
       for row in self.rule_graph.query(HAS_MULTI_NODES.format(rule)):
           if str(row[0]).lower().startswith("true"):
               return rdflib.BNode()
       for subject in self.graph.query(GET_BLANK_NODE.format(bf_property)):
           # set to first and exist loop
           blank_node = subject[0]
           break
       if not blank_node:
           blank_node = rdflib.BNode()
       return blank_node

    def populate_entity(self, bf_class):
        """Takes a BIBFRAME graph and MODS XML, extracts XPATH for each
        entity's property and adds to graph.

        Args:
            bf_class(rdflib.URIRef): Namespace URI
        Returns:
           rdflib.URIRef: URI of new entity
        """
        entity_uri = rdflib.URIRef("{}/{}".format(self.base_url, uuid.uuid1()))
        self.graph.add((entity_uri, rdflib.RDF.type, bf_class))
        self.update_linked_classes(bf_class, entity_uri)
        self.update_direct_properties(bf_class, entity_uri)
        self.update_ordered_linked_classes(bf_class, entity_uri)
        self.add_admin_metadata(entity_uri)
        return entity_uri     

    def remove_blank_nodes(self, bnode):
        """Recursively removes all blank nodes

        Args:
            bnode(rdflib.BNode): Blank 
        """
        for pred, obj in self.graph.predicate_objects(subject=bnode):
            self.graph.remove((bnode, pred, obj))
            if isinstance(obj, rdflib.BNode):
                self.remove_blank_nodes(obj)

    def replace_uris(self, old_uri, new_uri, excludes=[]):
        """Replaces all occurrences of an old uri with a new uri

        Args:
            old_uri(rdflib.URIRef): 
            new_uri(rdflib.URIRef):
            excludes(list): 
        """
        for pred, obj in graph.predicate_objects(subject=old_uri):
            if isinstance(obj, rdflib.BNode):
                self.remove_blank_nodes(obj)
            self.graph.remove((old_uri, pred, obj))
            if not pred in excludes:
                self.graph.add((new_uri, pred, obj))


    def update_direct_properties(self,
        entity_class, 
        entity):
        """Update the graph by adding all direct literal properties of the entity 
        in the graph.

        Args:
           entity_class (url): URL of the entity's class
           entity (rdflib.URIRef): RDFlib Entity
        """
        sparql = GET_DIRECT_PROPS.format(entity_class) 
        for dest_prop, rule in self.rules_graph.query(sparql):
            self.__handle_pattern__(entity, rule, dest_prop)
           
    def update_linked_classes(self,
        entity_class,
        entity):
        """Updates RDF Graph of linked classes

        Args:
           entity_class (url): URL of the entity's class
           entity (rdflib.URIRef): RDFlib Entity
        """
        sparql = GET_LINKED_CLASSES.format(entity_class)
        for dest_property, dest_class, prop, subj in \
            self.rules_graph.query(sparql):
            #! Should dedup dest_class here, return found URI or BNode
            sparql = GET_SRC_PROP.format(
                dest_class, 
                dest_property,
                entity_class, 
                KDS.PropertyLinker)
            for row in self.rules_graph.query(sparql):
                self.__handle_linked_pattern__(
                    entity=entity, 
                    destination_class=dest_class,
                    destination_property=dest_property,
                    target_property=prop,
                    target_subject=subj)

    def update_ordered_linked_classes(self,
        entity_class,
        entity):
        """Updates RDF Graph of linked classes

        Args:
           entity_class (url): URL of the entity's class
           entity (rdflib.URIRef): RDFlib Entity
        """
        sparql = GET_ORDERED_CLASSES.format(entity_class)
        for dest_property, dest_class, prop, subj in \
            self.rules_graph.query(sparql):
            for row in self.rules_graph.query(
                GET_SRC_PROP.format(dest_class,
                    dest_property,
                    entity_class,
                    KDS.OrderedPropertyLinker)):
                self.__handle_ordered__(entity_class, 
                    entity=entity,
                    destination_property=dest_propery,
                    destination_class = dest_class,
                    target_property=prop,
                    target_subject=subj)
                
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
