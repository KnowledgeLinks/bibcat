"""Helper Class and Functions for linking BIBFRAME 2.0 linked data with
Library of Congress id.loc.gov linked-data webservices"""
__author__ = "Jeremy Nelson, Mike Stabile"

import datetime
import sys
import unicodedata
import urllib.parse

import requests
import rdflib

from fuzzywuzzy import fuzz
import bibcat
from bibcat.linkers.linker import Linker

#! PREFIX should be generated from RDF Framework in the future
PREFIX = """PREFIX bf: <http://id.loc.gov/ontologies/bibframe/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>"""

#! BF should be from the RDF Framework Namespace manager
BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")
SKOS = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")

class LibraryOfCongressLinker(Linker):
    """Library of Congress Linked Data Linker"""
    ID_LOC_URL = "http://id.loc.gov/search/"

    def __init__(self, **kwargs):
        super(LibraryOfCongressLinker, self).__init__(**kwargs)
        self.base_url = kwargs.get('base_url', 'https://bibcat.org/')
        self.cutoff = kwargs.get("cutoff", 90)
        self.graph = kwargs.get("graph", None)
        self.punct_map = dict.fromkeys(i for i in range(sys.maxunicode)
                                       if unicodedata.category(chr(i)).startswith('P'))
        self.subject_sparql = kwargs.get("subject_sparql", SELECT_BF_SUBJECTS)

    def __link_subject__(self, term, subject_iri):
        """Function takes a term and queries LOC service
        Args:
            term(str): Term
            subject_iri(rdflib.URIRef): Subject IRI
        """
        lc_subject_url = LibraryOfCongressLinker.ID_LOC_URL
        label = term.translate(self.punct_map)
        lc_subject_url += "?" + urllib.parse.urlencode(
            {"q": label,
             "format": "json"})
        lc_subject_url += "&q=scheme:http://id.loc.gov/authorities/subjects"
        subject_result = requests.get(lc_subject_url)
        if subject_result.status_code < 400:
            lsch_iri, title = self.__process_loc_results__(
                subject_result.json(),
                label)
            if lsch_iri is None:
                return None, None
            for entity in self.graph.subjects(predicate=BF.subject,
                                              object=subject_iri):
                self.graph.add((entity, BF.subject, lsch_iri))
            bibcat.delete_iri(self.graph, subject_iri)
            return lsch_iri, title
        return None, None

    def __process_loc_results__(self, results, label):
        title, loc_uri, term_weights = None, None, dict()
        for row in results:
            if isinstance(row, dict):
                continue
            if row[0].startswith('atom:entry'):
                if row[2][0].startswith("atom:title"):
                    title = row[2][-1]
                if row[3][0].startswith("atom:link") and \
                    row[3][-1].get('type') is None:
                    loc_uri = rdflib.URIRef(row[3][-1].get('href'))
                    term_weights[str(loc_uri)] = {
                        "weight": fuzz.ratio(label, title),
                        "title": title}
        results = sorted(term_weights.items(), key=lambda x: x[1]['weight'])
        results.reverse()
        for row in results:
            loc_url = row[0]
            weight = row[1].get('weight')
            title = row[1].get('title')
            if weight >= self.cutoff:
                return rdflib.URIRef(loc_url), rdflib.Literal(title)
        return None, None

    def link_lc_subjects(self, topic_subject, raw_label):
        """Method takes a subject IRI and a label, first does a split on
        -- character which is commonly used to delimit complex LCSH

        Args:
            topic_subject(rdflib.BNode|rdflib.URIRef): Subject BNode or IRI
            label(str): Subject IRI's RDFS Label or RDF Value
        """
        def __add_topic__(loc_iri, value):
            self.graph.add((loc_iri, rdflib.RDF.type, BF.Topic))
            self.graph.add((loc_iri, rdflib.RDF.value, rdflib.Literal(value)))
        entities = self.graph.subjects(predicate=BF.subject,
                                       object=topic_subject)
        terms = raw_label.split("--")
        if len(terms) < 1:
            return
        elif len(terms) == 1:
            loc_iri, title = self.__link_subject__(terms[0], topic_subject)
            if loc_iri is None:
                return
            __add_topic__(loc_iri, title)
            for entity in entities:
                self.graph.add((entity, BF.subject, loc_iri))
            if isinstance(topic_subject, rdflib.BNode):
                bibcat.delete_bnode(self.graph, topic_subject)
            else:    
                bibcat.delete_iri(self.graph, topic_subject)
        # Assumes a complex subject, bases ordering on extract tokens
        # from split call
        else:
            rdf_list = []
            for term in terms:
                subject_iri, title = self.__link_subject__(term, topic_subject)
                if subject_iri is None:
                    # Create a local IRI and set term as rdf:value
                    subject_iri = rdflib.URIRef("{}topic/{}".format(
                        self.base_url,
                        bibcat.slugify(term)))
                    title = term
                __add_topic__(subject_iri, title)
                rdf_list.append(subject_iri)
            if len(rdf_list) < 1:
                return
            # Delete old subject if a Blank Node
            if isinstance(topic_subject, rdflib.BNode):
                bibcat.delete_bnode(self.graph, topic_subject)
                # Create a new topic_subject as an IRI
                topic_subject = rdflib.URIRef("{}topic/{}".format(
                    self.base_url,
                    bibcat.slugify(raw_label)))
            # Add topic_subject back as a bf:Topic and SKOS.OrganizedCollection
            self.graph.add((topic_subject, rdflib.RDF.type, BF.Topic))
            self.graph.add((topic_subject, 
                            rdflib.RDF.type, 
                            SKOS.OrderedCollection))
            self.graph.add((topic_subject, 
                            rdflib.RDFS.label, 
                            rdflib.Literal(raw_label)))
            self.graph.add((topic_subject,
                            SKOS.memberList,
                            bibcat.create_rdf_list(self.graph,
                                                   rdf_list)))


    def run(self, graph=None):
        """Runs linker on existing bf:subject Blank Nodes"""
        if graph is not None:
            self.graph = graph
            self.graph.namespace_manager.bind("skos", SKOS)
            result = self.graph.query(self.subject_sparql)
            bindings = result.bindings
        elif self.triplestore_url is not None:
            result = requests.post(self.triplestore_url,
                data={"query": self.subject_sparql,
                      "format": "json"})
            if result.status_code < 400:
                bindings = result.json().get('results').get('bindings')
            else:
                raise ValueError("Error {}\n\n{}".format(
                    result.status_code,
                    result.text))
        start = datetime.datetime.utcnow()
        print("Starting LCSH Linker Service at {}, total to process {:,}".format(
            start,
            len(bindings)))
        for i, row in enumerate(bindings):
            subject_iri = row.get('subject')
            label = row.get('label')
            self.link_lc_subjects(subject_iri, label)
            if not i%10 and i > 0:
                print(".", end="")
            if not i%100:
                print("{:,}".format(i), end="")
        end = datetime.datetime.utcnow()
        print("Finished LCSH Linker Service at {}, total time={} mins".format(
            end,
            (end-start).seconds /60.0))


SELECT_BF_SUBJECTS = PREFIX + """

SELECT DISTINCT ?subject ?label
WHERE {
	?subject rdf:type bf:Topic .
	OPTIONAL { ?subject rdfs:label ?label }
        OPTIONAL { ?subject rdf:value ?label }
} ORDER BY ?subject"""


SUBJECT_BNODES = PREFIX + """

SELECT ?instance ?label 
WHERE {
    ?instance bf:subject ?subject .
    ?subject rdf:value ?label .
    filter(isblank(?subject))
}"""

UPDATE_SUBJECT = PREFIX + """

DELETE {{
   ?instance bf:subject ?sub_bnode .
   ?sub_bnode ?p ?o .
}} INSERT {{
    BIND(<{0}> as ?lcsh)
    ?instance bf:subject ?lcsh .
}} WHERE {{
    BIND(<{1}> as ?instance)
    ?instance bf:subject ?sub_bnode .
    ?sub_bnode rdfs:label "{2}" .
}}"""
