"""BIBCAT is a RDF-based Bibliographic Catalog"""
import datetime
import re
import urllib.parse
import pkg_resources
import rdflib
from rdflib.term import _is_valid_uri

__author__ = "Jeremy Nelson, Mike Stabile, Jay Peterson"
__version__ = "0.0.5" #pkg_resources.get_distribution("bibcat").version

BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")

def clean_uris(graph):
    """Iterates through all URIRef subjects and objects and attempts to fix any
    issues with URL.

    Args:
        graph(rdflib.Graph): BIBFRAME RDF Graph
    """
    def fix_uri(uri):
        """Function attempts to take an invalid uri and return a valid URI

        Args:
            uri(str): Questionable URI
        """
        url_sections = urllib.parse.urlparse(str(uri))
        new_url = (url_sections.scheme,
                   url_sections.netloc,
                   urllib.parse.quote(url_sections.path),
                   urllib.parse.quote(url_sections.params),
                   urllib.parse.quote(url_sections.query),
                   urllib.parse.quote(url_sections.fragment))
        new_uri = rdflib.URIRef(
            str(urllib.parse.urlunparse(new_url)))
        replace_iri(graph, uri, new_uri)
    all_uri_sparql = """SELECT DISTINCT ?uri
        WHERE {
            ?uri ?p ?o .
            ?s ?p1 ?uri .
        FILTER(isIRI(?uri))
    }"""
    for iri in graph.query(all_uri_sparql):
        try:
            if _is_valid_uri(str(iri[0])) is False:
                fix_uri(iri[0])
        except rdflib.exceptions.SubjectTypeError:
            fix_uri(iri)

def create_rdf_list(graph, nodes):
    """Creates a RDF List with the ordering based on the nodes.
    Returns a blank node that functions in the object role for adding
    a triple.

    Args:
        graph(rdflib.Graph|rdflib.ConjuctiveGraph): Source graph
        nodes(list): Python list of nodes
    """
    if len(nodes) < 1:
        return rdflib.RDF.nil
    ordered_bnode = rdflib.BNode()
    graph.add((ordered_bnode, rdflib.RDF.first, nodes[0]))
    graph.add((ordered_bnode,
               rdflib.RDF.rest,
               create_rdf_list(graph, nodes[1:])))
    return ordered_bnode

def delete_bnode(graph, bnode):
    """Deletes blank node and associated triples

    Args:
        graph(rdflib.Graph|rdflib.ConjuctiveGraph): Graph
        bnode(rdflib.BNode): Blank node to delete
    """
    for pred, obj in graph.predicate_objects(subject=bnode):
        if isinstance(obj, rdflib.BNode):
            delete_bnode(graph, obj)
        graph.remove((bnode, pred, obj))
    for sub, pred in graph.subject_predicates(object=bnode):
        graph.remove((sub, pred, bnode))


def delete_iri(graph, entity_iri):
    """Deletes all triples associated with an entity in a graph

    Args:
        graph(rdflib.Graph|rdflib.ConjuctiveGraph): Graph
        entity_iri(rdflib.URIRef): IRI of entity
    """
    for pred, obj in graph.predicate_objects(subject=entity_iri):
        if isinstance(obj, rdflib.BNode):
            delete_bnode(graph, obj)
        graph.remove((entity_iri, pred, obj))
    for subj, pred in graph.subject_predicates(object=entity_iri):
        graph.remove((subj, pred, entity_iri))

def modified_bf_desc(**kwargs):
    """Adds a bf:adminMetadata property with a blank node for
    the entity. Optional agent_iri arg will add the agent_iri as a
    bf:descriptionModifier

    Args:
        graph((rdflib.Graph|rdflib.ConjuctiveGraph): Graph
        entity_iri(rdflib.URIRef): IRI of entity
        msg(str): Message the describes the modification to the
                  entity
        agent_iri(rdflib.URIRef): Agent IRI, can be None
    """
    graph = kwargs.get("graph")
    entity_iri = kwargs.get("entity_iri")
    msg = kwargs.get("msg")
    if msg is None:
        raise AttributeError("Message cannot be None")
    agent_iri = kwargs.get("agent_iri")
    bnode = rdflib.BNode()
    graph.add((bnode, rdflib.RDF.type, BF.AdminMetadata))
    graph.add((entity_iri, BF.adminMetadata, bnode))
    graph.add((bnode, rdflib.RDF.value, rdflib.Literal(msg)))
    graph.add((bnode,
               BF.changeDate,
               rdflib.Literal(datetime.datetime.utcnow().isoformat())))
    if agent_iri is not None:
        graph.add((bnode,
                   BF.descriptionModifier,
                   agent_iri))


def replace_iri(graph, old_iri, new_iri):
    """Replaces old IRI with a new IRI in the graph

    Args:

    ----
        graph: rdflib.Graph
        old_iri: rdflib.URIRef, Old IRI
        new_iri: rdflib.URIRef, New IRI
    """
    if old_iri == new_iri:
        # Otherwise deletes all occurrences of the iri in the
        # graph
        return
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
