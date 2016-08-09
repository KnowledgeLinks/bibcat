"""SPARQL Templates and direct Statements for BIBCAT Generators"""
try:
    from .generator import NS_MGR
# Failed relative import
except SystemError:
    from generator import NS_MGR
PREFIX = NS_MGR.prefix()

DELETE_WORK_BNODE = PREFIX + """
DELETE {{
    ?work ?p ?o 
}} WHERE {{
    <{0}> bf:instanceOf ?work .
    ?work ?p ?o
    filter isBlank(?work)
}}"""

GET_AVAILABLE_INSTANCES = PREFIX + """
SELECT ?instance 
WHERE {
    ?instance rdf:type bf:Instance .
    ?instance bf:instanceOf ?work .
    filter(isblank(?work))
}"""


GET_INSTANCE_CREATOR = PREFIX + """
SELECT ?name 
WHERE {{
    <{0}> relators:cre ?creator .
    OPTIONAL {{ <{0}> relators:aut  ?creator }}
    OPTIONAL {{ <{0}> relators:aus ?creator }}
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
    ?title bf:mainTitle ?mainTitle .
    FILTER(isuri(?work)) 
    FILTER CONTAINS("{0}", ?mainTitle)
}}"""


