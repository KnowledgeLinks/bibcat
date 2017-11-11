"""Geonames Web Service <http://www.geonames.org/> linker that resolves
geographic terms to Geonames URIs as a controlled vocabulary."""
__author__ = "Jeremy Nelson"


import urllib.parse

import rdflib
import requests

API_BASE = "http://api.geonames.org/"
IRI_BASE = "http://www.geonames.org/"
DEFAULT_PARAMS = {
    "q": None,
    "fuzzy": 0.8
}

def __top_result__(query_result, type_=None, class_=None):
    """Internal function takes a JSON query results and returns
    the top result as a rdflib.URIRef IRI if more than one.

    Args:
    ----
        query_result(dict): Query result
    """
    if query_result.get("totalResultsCount", 0) > 0:
        print(query_result.get("geonames")[0])
        
        top_result = query_result.get("geonames")[0]
        geo_id =  top_result.get("geonameId")
        place_iri = rdflib.URIRef("{}{}/".format(IRI_BASE, geo_id))
        if type_ is not None and type_.startswith("rdf"):
            output = rdflib.Graph()
            rdf_type = rdflib.RDFS.Resource
            if class_ is not None:
                rdf_type = class_
            output.add((place_iri, rdflib.RDF.type, rdf_type))
            output.add((place_iri, 
                        rdflib.RDFS.label, 
                        rdflib.Literal(top_result.get("name"))))
            return output
        return place_iri
            
            
            
        

def link_iri(term, username, type_=None, format_="json", class_=None):
    """Function takes a geographic term and a username and attempts
    resolve to a geonames IRI.

    Args:
    -----
        term(string): String
        username(string): Username for geonames API
    """
    DEFAULT_PARAMS["username"] = username
    DEFAULT_PARAMS["q"] = term
    if type_ is not None:
        DEFAULT_PARAMS["type"] = type_
    search_action = "search"
    if format_ is not None and format_.startswith("json"):
        search_action = "searchJSON"
    geo_url = "{}{}?{}".format(
        API_BASE,
        search_action,
        urllib.parse.urlencode(DEFAULT_PARAMS))
    result = requests.get(geo_url)
    if result.status_code < 400:
        if format_ and format_.startswith('json'):
            return __top_result__(result.json(), type_=type_, class_=class_)
        if type_ is "rdf":
            results_graph = rdflib.Graph()
            results_graph.parse(data=result.text, format="xml")
            return results_graph

        return result.text
