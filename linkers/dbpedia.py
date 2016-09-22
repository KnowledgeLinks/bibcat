"""Helper Class and Functions for linking BIBFRAME 2.0 linked data with DBPedia"""
__author__ = "Jeremy Nelson, Mike Stabile"

import rdflib
import requests
import urllib.parse

from .linker import Linker, NS_MGR

class DBPediaLinker(Linker):
    SPARQL_ENDPOINT = "http://dbpedia.org/sparql"

    def enhance_uri(self, uri, dbpedia_url, filters=[]):
        """Takes a URI,  parses DBPedia graph from DBpedia URI,
        and adds triples from dbpedia to uri in the triplestore.

        Args:
            uri(rdflib.URIRef): RDF URI of the entity in the triplestore
            dbpedia_uri(string): URL of DBPedia Resource
            filters(list): List of Namespaces or specific predicates to add
                           triplestore, default is empty list for adding
                           everything to triplestore
        """
        turtle_url = urllib.parse.urljoin(
            "http://dbpedia.org/",
            "data/{}.n3".format(dbpedia_url.split("/")[-1]))
        dbpedia_uri = rdflib.URIRef(dbpedia_url)
        dbpedia_resource = rdflib.Graph().parse(turtle_url, format='turtle')
        if len(filters) < 1:
            dbpedia_resource.add((dbpedia_uri, rdflib.OWL.sameAs, uri))
            return dbpedia_resource
        namespace_filters = []
        for filter_ in filters:
            if isinstance(filter_, rdflib.Namespace):
                namespace_filters.append(str(filter_))
                filters.pop(filter_)
        uri_graph = create_graph()
        uri_graph.add((uri, self.ns.owl.sameAs, dbpedia_uri))
        for predicate, object_ in dbpedia_resource.predicate_objects(
                subject=dbpedia_uri):
            if predicate in filters:
                uri_graph.add((uri, predicate, object_))
            for name_str in namespace_filters:
                if str(predicate).startswith(name_str):
                    uri_graph.add((uri, predicate, object_))
        return uri_graph

    def search_label(self,
                     label,
                     types=None):
        """Searches DBPedia using the RDFS label and restricting
        by DBPedia specific classes.

        Args:
            label(str): Label to search
            types(list): List of DBO classes to restrict search
        Returns:
            list: A list of resources that match the label
        """
        if types is None:
            types = [NS_MGR.dbo.Album,
                     NS_MGR.dbo.Book,
                     NS_MGR.dbo.Film]
        sparql = """SELECT DISTINCT ?resource
        WHERE {{
            ?resource rdfs:label ?label .
            ?resource rdf:type <{0}> .
            FILTER regex(?label, "^{1}", "i")
        }} LIMIT 100"""
        output = []
        for type_ in types:
            query = sparql.format(type_, label)
            result = requests.post(self.SPARQL_ENDPOINT,
                                   data={"query": query,
                                         "format": "json"})
            if result.status_code < 399:
                results = result.json().get('results', {})
                if len(results) < 1:
                    continue
                bindings = results.get('bindings')
                if len(bindings) < 1:
                    continue
                for row in bindings:
                    resource = row.get('resource')
                    resource['dbo:class'] = type_
                    output.append(resource)
        return output

    def __init__(self, **kwargs):
        super(DBPediaLinker, self).__init__(**kwargs)
