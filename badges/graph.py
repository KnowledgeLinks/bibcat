"""
 graph module is based on the latest version of Open Badges Specification at 
 https://openbadgespec.org/

"""
__author__ = "Jeremy Nelson"
__license__ = "GPLv3"

import rdflib

OBI = rdflib.Namespace("https://w3id.org/openbadges#")
RDF = rdflib.RDF
SCHEMA = rdflib.Namespace("https://schema.org/")

PREFIX = """PREFIX obi: <{}>
PREFIX rdf: <{}>
PREFIX schema: <{}>""".format(OBI, RDF, SCHEMA)

CLASS_EXISTS_SPARQL = """{}
SELECT DISTINCT ?entity
WHERE {{{{
  ?entity schema:alternativeName "{{}}"^^xsd:string .
}}}}""".format(PREFIX)

CHECK_ISSUER_SPARQL = """{}
SELECT DISTINCT ?entity
WHERE {{{{
   ?entity obi:url <{{}}> .
}}}}""".format(PREFIX)

CHECK_PERSON_SPARQL = """{}
SELECT DISTINCT ?entity 
WHERE {{{{
  ?entity obi:email "{{}}"^^xsd:string .
}}}}""".format(PREFIX)

FIND_ASSERTION_SPARQL = """{}
SELECT DISTINCT *
WHERE {{{{
  ?subject obi:uid "{{}}"^^xsd:string .
  ?subject obi:recipient ?IdentityObject .
  ?subject obi:issuedOn ?DateTime .
  ?subject obi:BadgeClass ?badgeURI .
  ?badgeURI schema:alternativeName ?badgeClass .
}}}}""".format(PREFIX)


FIND_CLASS_SPARQL = """{}
SELECT DISTINCT *
WHERE {{{{
  ?class rdf:type openbadge:BadgeClass .
  ?class obi:name ?name .
  ?class obi:description ?description .
  ?class obi:issuer ?issuer .
  ?class schema:alternativeName "{{}}"^^xsd:string .
}}}}""".format(PREFIX)

FIND_CLASS_IMAGE_SPARQL = """{}
SELECT DISTINCT ?image
WHERE {{{{
  ?subject schema:alternativeName "{{}}"^^xsd:string .
  ?subject iana:describes ?image .
}}}}""".format(PREFIX)

FIND_CRITERIA_SPARQL = """{}
SELECT ?name ?criteria
WHERE {{{{
  ?class schema:alternativeName "{{}}"^^xsd:string .
  ?class schema:educationalUse ?criteria .
  ?class schema:name ?name .
}}}}""".format(PREFIX)

FIND_IMAGE_SPARQL = """{}
SELECT DISTINCT ?image
WHERE {{{{
  ?subject openbadge:uid "{{}}"^^xsd:string  .
  ?subject ldp:contains ?image .
}}}}""".format(PREFIX)

FIND_KEYWORDS_SPARQL = """{}
SELECT ?keyword
WHERE {{{{
   ?subject schema:alternativeName "{{}}"^^xsd:string .
   ?subject obi:keywords ?keyword .
}}}}""".format(PREFIX)

IDENT_OBJ_SPARQL = """{}
SELECT DISTINCT *
WHERE {{{{
  <{{0}}> openbadge:identity ?identHash .
  <{{0}}> openbadge:salt ?salt .
}}}}""".format(PREFIX)

UPDATE_UID_SPARQL = """{}
INSERT DATA {{{{
    <{{}}> openbadge:uid "{{}}"^^xsd:string
}}}}""".format(PREFIX)

UPDATE_BADGE_CLASS = """{}
INSERT {{{{
  <> obi:issuer <{{}}> .
  <> obi:name "{{}}" .
  <> obi:description "{{}}" .
  <> schema:alternativeName "{{}}" .
  <> 
}}}}
WHERE {{{{ }}}}""".format(PREFIX)

def default_graph():
    graph = rdflib.Graph()
    graph.namespace_manager.bind('obi', OBI)
    graph.namespace_manager.bind('rdf', rdflib.RDF)
    graph.namespace_manager.bind('schema', SCHEMA)
    return graph


