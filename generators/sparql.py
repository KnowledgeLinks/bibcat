"""SPARQL Templates and direct Statements for BIBCAT Generators"""
try:
    from .generator import NS_MGR
# Failed relative import
except SystemError:
    from generator import NS_MGR

NS_MGR.bind("bf", "http://id.loc.gov/ontologies/bibframe/")
PREFIX = NS_MGR.prefix()

DELETE_COLLECTION_BNODE = PREFIX + """
DELETE {{
    ?collection ?p ?o .
    <{0}> bf:partOf ?collection
}} 
INSERT {{ }}
WHERE {{
    <{0}> bf:partOf ?collection .
    ?collection ?p ?o
    filter isBlank(?collection)
}}"""


DELETE_WORK_BNODE = PREFIX + """
DELETE {{
    ?work ?p ?o .
    <{0}> bf:instanceOf ?work
}} 
INSERT {{ }}
WHERE {{
    <{0}> bf:instanceOf ?work .
    ?work ?p ?o
    filter isBlank(?work)
}}"""

GET_AVAILABLE_COLLECTIONS = PREFIX + """
SELECT ?instance ?org ?item ?label
WHERE {
    ?instance rdf:type bf:Instance .
    ?instance bf:partOf ?collection .
    ?collection rdf:type pcdm:Collection .
    ?collection rdfs:label ?label .
    ?item bf:itemOf ?instance .
    ?item bf:heldBy ?org
    filter(isblank(?collection))
}"""

GET_AVAILABLE_INSTANCES = PREFIX + """
SELECT ?instance 
WHERE {
    ?instance rdf:type bf:Instance .
    ?instance bf:instanceOf ?work .
    filter(isblank(?work))
}"""



GET_INSTANCE_CREATOR = PREFIX + """
SELECT ?name ?creator
WHERE {{
    <{0}> <{1}> ?creator .
    OPTIONAL {{ ?creator rdfs:label ?name }} 
    OPTIONAL {{ ?creator schema:name ?name }}
    OPTIONAL {{ ?creator schema:alternativeName ?name }}
}}"""

GET_INSTANCE_TITLE = PREFIX + """
SELECT ?mainTitle ?subTitle
WHERE {{
    <{0}> bf:title ?title .
    ?title a bf:InstanceTitle .
    ?title bf:mainTitle ?mainTitle .
    OPTIONAL {{ ?title bf:subtitle ?subTitle }}
}}"""

GET_INSTANCE_WORK_BNODE_PROPS = PREFIX + """
SELECT ?pred ?obj
WHERE {{
    <{0}> bf:instanceOf ?work .
    ?work ?pred ?obj .
    filter(isblank(?work))
}}"""

FILTER_COLLECTION = PREFIX + """
SELECT ?collection ?instance
WHERE {{
    ?collection rdf:type bf:Work .
    ?collection rdf:type pcdm:Collection .
    ?collection rdfs:label ?label .
    ?collection bf:hasPart ?instance .
    <{0}> bf:itemOf ?instance .
    <{0}> bf:heldBy <{1}> 
    FILTER(isiri(?collection))
    FILTER CONTAINS("{2}", ?label)
}}"""

FILTER_WORK_CREATOR = PREFIX + """
SELECT ?work
WHERE {{
    ?work rdf:type bf:Work .
    ?work relators:cre ?creator .
    OPTIONAL {{ ?creator schema:name ?name }}
    OPTIONAL {{ ?creator schema:alternativeName ?name }}
    FILTER(isuri(?work))
    FILTER CONTAINS("{0}", ?name)
}}"""

FILTER_WORK_TITLE = PREFIX + """
SELECT ?work
WHERE {{
    ?work rdf:type bf:Work .
    ?work bf:title ?title .
    ?title ?mainTitle """ + '"""{0}""" .' + """
    FILTER(isuri(?work)) 
}}"""
