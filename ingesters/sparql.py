import rdflib
from rdfframework.utilities import RdfNsManager

PREFIX  = NSM.get_prefix()

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
    ?subj rdf:type <{3}> .
    OPTIONAL {{ ?subj kds:srcPropUri ?prop }} .
    OPTIONAL {{ ?subj kds:srcPropXpath ?prop }} .
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
SELECT DISTINCT ?agent
WHERE {{
    ?agent rdf:type <{0}> .
    ?agent <{1}>  "{2}" .
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

DEDUP_ENTITIES = PREFIX + """
SELECT DISTINCT ?entity
WHERE {{
    ?entity <{0}> ?identifier .
    ?identifier rdf:type <{1}> .
    ?identifier rdf:value "{2}" .
}}"""

DEDUP_AGENTS = PREFIX + """
SELECT DISTINCT ?agent
WHERE {{
    ?agent rdf:type <{0}> .
    ?agent <{1}>  "{2}" .
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
