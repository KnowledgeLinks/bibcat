"""Module contains SPARQL templates for managing a BIBCAT instance"""
__author__ = "Jeremy Nelson, Mike Stabile"
import sys

try:
    from .ingester import PROJECT_BASE, NS_MGR
# Failed relative import
except SystemError:
    from ingester import PROJECT_BASE, NS_MGR
sys.path.append(PROJECT_BASE)
try:
    import rdfw as rdfframework
except ImportError:
    pass


NSM = NS_MGR

PREFIX = NSM.prefix()

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
    OPTIONAL {{ ?subj kds:srcPropUri ?src_prop }} .
    OPTIONAL {{ ?subj kds:srcPropXpath ?src_prop }} .
    OPTIONAL {{ ?subj kds:srcPropKey ?src_prop }} .
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
    ?subj kds:destClassUri <{0}> .
    ?subj kds:destPropUri <{1}> .
    ?subj kds:linkedClass <{2}> .
    ?subj kds:linkedRange <{3}> .
    ?subj rdf:type <{4}> .
    OPTIONAL {{ ?subj kds:srcPropUri ?prop }} .
    OPTIONAL {{ ?subj kds:srcPropXpath ?prop }} .
    OPTIONAL {{ ?subj kds:srcPropKey ?prop }} .
}}"""

HAS_MULTI_NODES = PREFIX + """
SELECT DISTINCT ?is_multi_nodes
WHERE {{
    <{0}> kds:hasIndividualNodes ?is_multi_nodes .
}}"""

DEDUP_ENTITIES = PREFIX + """
SELECT DISTINCT ?entity
WHERE {{
    ?entity <{0}> ?identifier .
    ?identifier rdf:type <{1}> .
    ?identifier rdf:value "{2}" .
}}"""

DEDUP_AGENTS = PREFIX + """
SELECT DISTINCT ?agent ?type
WHERE {{
    ?agent rdf:type ?type .
    ?agent <{0}> ?label .
    OPTIONAL {{ ?agent a bf:Person }} 
    OPTIONAL {{ ?agent a bf:Organization }} 
    filter regex(?label, "{1}")
}}"""

DEDUP_PERSON_ORG = PREFIX + """
SELECT DISTINCT ?agent ?label ?type
WHERE {
    ?agent a ?type .
    OPTIONAL { ?agent a bf:Person } .
    OPTIONAL { ?agent a bf:Organization } .
    OPTIONAL { ?agent rdfs:label ?label } .
    OPTIONAL { ?agent schema:alternativeName ?label } .
}"""

ENTITY_IRI_PATTERN = PREFIX + """
SELECT ?iri_pattern ?srcSelection ?srcFilter
WHERE {{
    ?subj rdf:type kds:IRIPattern .
    ?subj kds:destClassUri <{0}> .
    ?subj kds:iriPattern ?iri_pattern .
    ?subj <{1}> ?srcSelection .
    ?subj <{2}> ?srcFilter .
}}"""

GET_ADDL_PROPS = PREFIX + """
SELECT ?pred ?obj
WHERE {{
  <{0}> kds:destAdditionalPropUris ?subj .
  ?subj ?pred ?obj .
}}"""

GET_AGENTS = PREFIX + """
SELECT DISTINCT ?subject ?value
WHERE {{
    ?subject rdf:type <{0}> .
    ?subject <{1}> ?value .
}}"""

GET_BLANK_NODE = PREFIX + """
SELECT ?subject 
WHERE {{
    ?instance <{0}> ?subject .
}}"""

DEDUP_ENTITIES = PREFIX + """
SELECT DISTINCT ?entity
WHERE {{
    ?entity <{0}> ?identifier .
    ?identifier rdf:type <{1}> .
    ?identifier rdf:value "{2}" .
}}"""

GET_ADDL_PROPS = PREFIX + """
SELECT ?pred ?obj
WHERE {{
  <{0}> kds:destAdditionalPropUris ?subj .
  ?subj ?pred ?obj .
}}"""

GET_BLANK_NODE = PREFIX + """
SELECT ?subject 
WHERE {{
    ?instance <{0}> ?subject .
}}"""

GET_IDENTIFIERS = PREFIX + """
SELECT ?entity ?ident_value
WHERE {{
    ?entity rdf:type <{0}> .
    ?entity bf:identifiedBy ?identifier .
    ?identifier rdf:type <{1}> .
    ?identifier rdf:value ?ident_value .
}}"""

GET_ORDERED_MARC_LIST = PREFIX + """
SELECT ?marc
WHERE {{
    ?subj kds:srcOrderedPropUri/rdf:rest*/rdf:first ?marc .
    ?subj kds:destClassUri <{0}> .
}}"""


