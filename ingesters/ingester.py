"""BIBFRAME 2.0 ingester class helper functions"""
__author__ = "Jeremy Nelson, Mike Stabile"

import datetime
import inspect
import logging
import os
import sys
import uuid
import rdflib
import requests


# get the current file name for logs and set logging levels
try:
    MNAME = inspect.stack()[0][1]
except:
    MNAME = "ingesters"
MLOG_LVL = logging.DEBUG
logging.basicConfig(level=logging.DEBUG)

BIBCAT_BASE = os.path.abspath(
    os.path.split(
        os.path.dirname(__file__))[0])
PROJECT_BASE = os.path.split(BIBCAT_BASE)[0]
sys.path.append(os.path.join(PROJECT_BASE))
sys.path.append(os.path.join(PROJECT_BASE, "rdfw",))
HIDE_LG = logging.getLogger("requests")
HIDE_LG.setLevel(logging.CRITICAL)
try:
    from instance import config
    from rdfframework import getframework as rdfw
    from rdfframework.utilities import DictClass, make_class
    from rdfframework.utilities.uriconvertor import RdfNsManager
except ImportError:
    logging.error("Error importing {}".format(PROJECT_BASE))
try:
    VERSION_PATH = os.path.join(
        BIBCAT_BASE,
        "VERSION")
    with open(VERSION_PATH) as version:
        __version__ = version.read().strip()
except:
    __version__ = "unknown"
#FW = rdfw.get_framework(config=config, reset=True, root_file_path=PROJECT_BASE)
#FW.ns_obj.log_level = logging.CRITICAL
#NS_MGR = FW.ns_obj
NS_MGR = RdfNsManager(config=config)
config = DictClass(config.__dict__)

#print(json.dumps(FW.rdf_linker_dict,indent=4))

class Ingester(object):
    """Base class for transforming various metadata format/vocabularies to
    BIBFRAME RDF Linked Data"""

    def __init__(self, **kwargs):
        self.base_url = kwargs.get("base_url")
        if not self.base_url:
            if config.BASE_URL:
                self.base_url = config.BASE_URL
            else:
                self.base_url = "http://bibcat.org/"
        if "graph" in kwargs:
            self.graph = kwargs.get("graph")
        else:
            self.graph = new_graph()
        if not "rules_ttl" in kwargs:
            raise ValueError("Ingester Requires Rules Turtle file name")
        self.rules_graph = new_graph()
        rules = kwargs.get("rules_ttl")
        if isinstance(rules, str):
            rules = [rules, ]
        for name in rules:
            # Base ttl file in rdfw-definitions
            default_filepath = os.path.join(
                BIBCAT_BASE,
                "rdfw-definitions",
                name)
            if os.path.exists(default_filepath):
                self.rules_graph.parse(default_filepath, format='turtle')
                NS_MGR.load(default_filepath)
            # Custom ttl files in the project's custom dir
            custom_filepath = os.path.join(
                PROJECT_BASE,
                "custom",
                name)
            if os.path.exists(custom_filepath):
                self.rules_graph.parse(custom_filepath, format='turtle')
                NS_MGR.load(custom_filepath)
        self.source = kwargs.get("source")
        self.triplestore_url = kwargs.get(
            "triplestore_url",
            "http://localhost:9999/blazegraph/sparql")
        self.__queries__ = dict()
        #self.__additional_entities__()


    def __generate_uri__(self):
        """Method generates an URI based on the base_url"""
        uid = uuid.uuid1()
        if self.base_url.endswith("/"):
            pattern = "{0}{1}"
        else:
            pattern = "{0}/{1}"
        return rdflib.URIRef(pattern.format(self.base_url, uid))

    def __pattern_uri__(self, entity_class):
        """Method checks for URI Pattern rule and returns an IRI
        if present, should be overridden by child ingesters.

        Args:
            entity_class (rdflib.URIRef): Entity Class to search
        """
        pass
        

    def add_admin_metadata(self, entity):
        """Takes a graph and adds the AdminMetadata for the entity

        Args:
            entity (rdflib.URIRef): URI of the entity
        """
        generate_msg = "Generated by BIBCAT version {} from KnowledgeLinks.io"
        generation_process = rdflib.BNode()
        self.graph.add((generation_process,
                        rdflib.RDF.type,
                        NS_MGR.bf.GenerationProcess))
        self.graph.add((generation_process,
                        NS_MGR.bf.generationDate,
                        rdflib.Literal(
                            datetime.datetime.utcnow().isoformat())))
        self.graph.add((generation_process,
                        rdflib.RDF.value,
                        rdflib.Literal(generate_msg.format(__version__),
                                       lang="en")))
        #! Should add bibcat's current git MD5 commit
        self.graph.add(
            (entity,
             NS_MGR.bf.generationProcess,
             generation_process)
        )

    def __additional_entities__(self):
        """Queries Rules graph for entities to add to triplestore as
        constants"""
        constants = new_graph()
        for subject in self.rules_graph.subjects(
                object=NS_MGR.kds.AddEntity):
            for predicate, object_ in self.rules_graph.predicate_objects(
                    subject=subject):
                if object_ != NS_MGR.kds.AddEntity:
                    constants.add((subject, predicate, object_))
        result = requests.post(self.triplestore_url,
                               data=constants.serialize(format='turtle'),
                               headers={"Content-Type": "text/turtle"})
        if result.status_code > 399:
            raise ValueError("Could add entities to triplestore")



    def add_to_triplestore(self):
        "Sends RDF graph via POST to add to triplestore"
        add_result = requests.post(
            self.triplestore_url,
            data=self.graph.serialize(format='xml'),
            headers={"Content-Type": "application/rdf+xml"})
        if add_result.status_code > 399:
            logging.error("Could not add graph to {}, status={}".format(
                self.triplestore_url,
                add_result.status_code))

    def clean_rdf_types(self):
        """Removes all Literal and Blank Nodes set as object to rdf:type"""
        for subj, obj in self.graph.subject_objects(
            predicate=NS_MGR.rdf.type):
            if not isinstance(obj, rdflib.URIRef):
                self.graph.remove((subj, NS_MGR.rdf.type, obj))
            

    def deduplicate_agents(self, filter_class, agent_class, calculate_uri=None):
        """Deduplicates graph

        Args:
            filter_class(rdflib.URIRef): Filter class URI
            agent_class(rdflib.URIRef): Agent BF class
            calculate_uri(rdflib.URIRef): Function for calculating a default URI
                                          if agent_class is not found, default
                                          is None.
        """
        results = []
        query_key = "{}{}".format(filter_class, agent_class)
        if query_key in self.__queries__:
            results = self.__queries__[query_key]
        else:
            sparql = GET_AGENTS.format(agent_class, filter_class)
            results = [r for r in self.graph.query(sparql)]
            self.__queries__[query_key] = results 
        for row in results:
            agent_uri, value = row
            sparql = DEDUP_AGENTS.format(
                filter_class,
                value)
            result = requests.post(
                self.triplestore_url,
                data={"query": sparql,
                      "format": "json"})
            if result.status_code > 399:
                raise ValueError("Could not deduplicate {}".format(agent_class))
            bindings = result.json().get('results', dict()).get('bindings', [])
            # Agent doesn't exit in triplestore 
            if len(bindings) < 1:
                # Checks rules_ttl for any defined agents that match filter_class
                new_agent_uri = self.rules_graph.value(predicate=filter_class,
                    object=rdflib.Literal(value))
                # Calls custom function to generate new_agent_uri
                if calculate_uri is not None:
                    new_agent_uri = calculate_uri(self.source)
                elif new_agent_uri is None:
                    # Add new URI with defaults
                    new_agent_uri = self.__generate_uri__()
            else:
                new_agent_uri = rdflib.URIRef(bindings[0].get("agent").get("value"))
            for subject, pred in self.graph.subject_predicates(object=agent_uri):
                self.graph.remove((subject, pred, agent_uri))
                self.graph.add((subject, pred, new_agent_uri))
            for pred, obj in self.graph.predicate_objects(subject=agent_uri):
                self.graph.remove((agent_uri, pred, obj))
                self.graph.add((new_agent_uri, pred, obj))


    def new_existing_bnode(self, bf_property, rule):
        """Returns existing blank node or a new if it doesn't exist

        Args:
            bf_property (str): RDF property URI
            rule (rdflib.URIRef): RDF subject of the map rule

        Returns:
            rdflib.BNode: Existing or New blank node
        """
        blank_node = None
        for row in self.rules_graph.query(HAS_MULTI_NODES.format(rule)):
            if str(row[0]).lower().startswith("true"):
                return rdflib.BNode()
        for subject in self.graph.query(GET_BLANK_NODE.format(bf_property)):
            # set to first and exist loop
            blank_node = subject[0]
            break
        if not blank_node:
            blank_node = rdflib.BNode()
        return blank_node

    def populate_entity(self, bf_class, existing_uri=None):
        """Takes a BIBFRAME graph and MODS XML, extracts info for each
        entity's property and adds to graph.

        Args:
            bf_class(rdflib.URIRef): Namespace URI
        Returns:
           rdflib.URIRef: URI of new entity
        """
        if existing_uri:
            entity_uri = existing_uri
        else:
            # Check for custom IRIPattern
            entity_uri = self.__pattern_uri__(bf_class)
            # Finally generate an IRI from the default patterns
            if not entity_uri:
                entity_uri = self.__generate_uri__()
        self.graph.add((entity_uri, rdflib.RDF.type, bf_class))
        self.update_linked_classes(bf_class, entity_uri)
        self.update_direct_properties(bf_class, entity_uri)
        self.update_ordered_linked_classes(bf_class, entity_uri)
        self.add_admin_metadata(entity_uri)
        self.clean_rdf_types()
        return entity_uri

    def reify_agents(self):
        """Searches existing graph for matching rules, substituting existing IRI
        for new Agent IRI"""
        pass

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
        for pred, obj in self.graph.predicate_objects(subject=old_uri):
            if isinstance(obj, rdflib.BNode):
                self.remove_blank_nodes(obj)
            self.graph.remove((old_uri, pred, obj))
            if not pred in excludes:
                self.graph.add((new_uri, pred, obj))

    def transform(self, source=None, instance_uri=None, item_uri=None):
        """Takes new source, sets new graph, and creates a BF.Instance and
        BF.Item entities

        Args:
            source: New source, could be URL, XML, or CSV row
            instance_uri(rdflib.URIRef): Existing Instance URI, defaults to None
            item_uri(rdflib.URIRef): Existing Item URI, defaults to None

        Returns:
            tuple: BIBFRAME Instance and Item
        """
        if source is not None:
            self.source = source
            self.graph = new_graph()
        bf_instance = self.populate_entity(NS_MGR.bf.Instance, instance_uri)
        bf_item = self.populate_entity(NS_MGR.bf.Item, item_uri)
        self.graph.add((bf_item, NS_MGR.bf.itemOf, bf_instance))
        return bf_instance, bf_item

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
            self.__handle_pattern__(
                entity=entity,
                rule=rule,
                destination_property=dest_prop)

    def update_linked_classes(self,
                              entity_class,
                              entity):
        """Updates RDF Graph of linked classes

        Args:
           entity_class (url): URL of the entity's class
           entity (rdflib.URIRef): RDFlib Entity
        """
        query_key = "linked_{}".format(entity_class)
        if query_key in self.__queries__:
            results = self.__queries__[query_key]
        else:
            sparql = GET_LINKED_CLASSES.format(entity_class)
            results = [r for r in self.rules_graph.query(sparql)]
            self.__queries__[query_key] = results
        for dest_property, dest_class, prop, subj in results:
            #! Should dedup dest_class here, return found URI or BNode
            if isinstance(dest_property, rdflib.BNode):
                self.__handle_linked_bnode__(
                    bnode=dest_property,
                    entity=entity,
                    destination_class=dest_class,
                    target_property=prop,
                    target_subject=subj)
                continue
            query_prop_key = "prop_{0}{1}{2}{3}".format(
                dest_class,
                dest_property,
                entity_class,
                prop)
            if query_prop_key in self.__queries__:
                props_result = self.__queries__[query_prop_key]
            else: 
                sparql_prop = GET_SRC_PROP.format(
                    dest_class,
                    dest_property,
                    entity_class,
                    prop,
                    NS_MGR.kds.PropertyLinker)
                props_result = [r for r in self.rules_graph.query(sparql_prop)]
                self.__queries__[query_prop_key] = props_result
            for row in props_result:
                self.__handle_linked_pattern__(
                    entity=entity,
                    destination_class=dest_class,
                    destination_property=dest_property,
                    rule=row[0],
                    target_property=prop,
                    target_subject=subj)
            # Identifies Work and Instance subclasses
            if not hasattr(self, "__handle_subclasses__"):
                continue
            ident_key = "ident_{0}{1}{2}{3}".format(
                dest_class,
                dest_property,
                entity_class,
                prop)
            if ident_key in self.__queries__:
                ident_results = self.__queries__[ident_key]
            else:
                identifier_sparql = GET_SRC_PROP.format(
                    dest_class,
                    dest_property,
                    entity_class,
                    prop,
                    NS_MGR.kds.ClassIdentifierLinker)
                ident_results = [r for r in self.rules_graph.query(
                    identifier_sparql)]
                self.__queries__[ident_key] = ident_results
            for row in ident_results:
                self.__handle_subclasses__(
                    entity=entity,
                    destination_class=dest_class,
                    destination_property=dest_property,
                    rule=row[0],
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
        query_key = "ordered_{}".format(entity_class)
        if query_key in self.__queries__:
            results = self.__queries__[query_key]
        else:
            sparql = GET_ORDERED_CLASSES.format(entity_class)
            results = [r for r in self.rules_graph.query(sparql)]
        for dest_property, dest_class, prop, subj in results:
            self.logger.debug("""Entity: class={} uri={}
Destination Property={} Destination Class={} 
Target Property={} Target_Class={}""".format(
    entity_class,
    entity,
    dest_property,
    dest_class,
    prop,
    subj))  
            prop_key = "ordered-prop_{0}{1}{2}{3}".format(
                dest_class,
                dest_property,
                entity_class,
                prop)
            if prop_key in self.__queries__:
                prop_results = self.__queries__[prop_key]
            else:
                prop_sparql = GET_SRC_PROP.format(
                    dest_class,
                    dest_property,
                    entity_class,
                    prop,
                    NS_MGR.kds.OrderedPropertyLinker)
                prop_results = [r for r in self.rules_graph.query(prop_sparql)]
                self.__queries__[prop_key] = prop_results
            for row in prop_results:
                self.__handle_ordered__(entity_class=entity_class,
                                        entity=entity,
                                        rule=row[0],
                                        destination_property=dest_property,
                                        destination_class=dest_class,
                                        target_property=prop,
                                        target_subject=subj)

def new_graph():
    """Function creates a new graph with RDF Framework namespace
    Manager"""
    # setup log
    lg = logging.getLogger("%s-%s" % (MNAME, inspect.stack()[0][3]))
    lg.setLevel(MLOG_LVL)
    graph = rdflib.Graph(namespace_manager=NS_MGR)
    return graph

try:
    from .sparql import GET_ORDERED_CLASSES, GET_SRC_PROP, GET_LINKED_CLASSES,\
        GET_AGENTS, GET_DIRECT_PROPS, DEDUP_AGENTS, GET_BLANK_NODE,\
        HAS_MULTI_NODES
    
# Relative import failed
except SystemError:
    from sparql import GET_ORDERED_CLASSES, GET_SRC_PROP, GET_LINKED_CLASSES,\
        GET_AGENTS, GET_DIRECT_PROPS, DEDUP_AGENTS, GET_BLANK_NODE,\
        HAS_MULTI_NODES

