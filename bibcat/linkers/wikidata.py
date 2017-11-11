"""Provides enhancement of existing bibliographic data by consuming info about
the entity from https://www.wikidata.org/"""
 
__author__ = "Jeremy Nelson"

import requests
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

def link_term(term, number=1):
    """Function takes a term and attempts to lookup best
    match on wikidata

    Args:
        term(str): Phrase
        number(int): Number of results to return
    """
    params = {"query": sparql_query,
              "format": "json"}
    
PREFIX = """PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wds: <http://www.wikidata.org/entity/statement/>
PREFIX wdv: <http://www.wikidata.org/value/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX bd: <http://www.bigdata.com/rdf#>"""


