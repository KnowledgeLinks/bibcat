"""SPARQL Templates and direct Statements for BIBCAT Generators"""
try:
    from .generator import NS_MGR
# Failed relative import
except SystemError:
    from generator import NS_MGR
PREFIX = NS_MGR.prefix()

GET_AVAILABLE_INSTANCES = PREFIX + """
SELECT ?instance 
WHERE {
    ?instance rdf:type bf:Instance .
    ?instance bf:instanceOf ?work .
    filter(isblank(?work))
}"""

GET_INSTANCE_TITLE = PREFIX + """
SELECT ?mainTitle ?subTitle
WHERE {{
    <{0}> bf:title ?title .
    ?title a bf:InstanceTitle .
    ?title bf:mainTitle ?mainTitle .
    OPTIONAL {{ ?title bf:subtitle ?subTitle }}
}}"""

FILTER_WORK_TITLE = PREFIX + """
SELECT ?work
WHERE {{
    ?work rdf:type ?Work .
    ?work bf:title ?title .
    ?title bf:mainTitle ?mainTitle .
    FILTER(isuri(?work)) 
    FILTER CONTAINS("{0}", ?mainTitle)
}}"""


