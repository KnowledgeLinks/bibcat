"""BIBCAT is a RDF-based Bibliographic Catalog"""
import re
import urllib.parse
import pkg_resources
import rdflib
__author__ = "Jeremy Nelson, Mike Stabile, Jay Peterson"
__version__ = pkg_resources.get_distribution("bibcat").version

def clean_uris(graph):
    """Iterates through all URIRef subjects and objects and attempts to fix any
    issues with URL.

    Args:
        graph(rdflib.Graph): BIBFRAME RDF Graph
    """
    def fix_uri(uri):
       url_sections = urllib.parse.urlparse(str(uri))
       new_url = (url_sections.scheme,
                  url_sections.netloc,
                  urllib.parse.quote(url_sections.path),
                  urllib.parse.quote(url_sections.params),
                  urllib.parse.quote(url_sections.query),
                  urllib.parse.quote(url_sections.fragment))
       new_uri = rdflib.URIRef(
           str(urllib.parse.urlunparse(new_url)))
       for pred, obj in graph.predicate_objects(subject=uri):
           graph.remove((uri, pred, obj))
           graph.add((new_uri, pred, obj)) 
       for subj, pred in graph.subject_predicates(object=uri):
           graph.remove((subj, pred, uri))
           graph.add((subj, pred, new_uri))
    ALL_URI_SPARQL = """SELECT DISTINCT ?uri
        WHERE {
            ?uri ?p ?o .
            ?s ?p1 ?uri .
        FILTER(isIRI(?uri))
    }"""
    for iri in graph.query(ALL_URI_SPARQL):
         try:
             rdflib.util.check_subject(str(iri))
         except rdflib.exceptions.SubjectTypeError:
             fix_uri(iri)

def replace_iri(graph, old_iri, new_iri):
    """Replaces old IRI with a new IRI in the graph

    Args:

    ----
        graph: rdflib.Graph
        old_iri: rdflib.URIRef, Old IRI
        new_iri: rdflib.URIRef, New IRI
    """
    for pred, obj in graph.predicate_objects(subject=old_iri):
        graph.add((new_iri, pred, obj))
        graph.remove((old_iri, pred, obj))
    for subj, pred in graph.subject_predicates(object=old_iri):
        graph.add((subj, pred, new_iri))
        graph.remove((subj, pred, old_iri))


def slugify(value):
    """
    Converts to lowercase, removes non-word characters (alphanumerics and
    underscores) and converts spaces to hyphens. Also strips leading and
    trailing whitespace. Adapted from Django's slugify function
    """
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '-', value)


def wikify(value):
    """Converts value to wikipedia "style" of URLS, removes non-word characters
    and converts spaces to hyphens and leaves case of value.
    """
    value = re.sub(r'[^\w\s-]', '', value).strip()
    return re.sub(r'[-\s]+', '_', value)



