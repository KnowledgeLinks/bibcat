"""Helper Class and Functions for linking BIBFRAME 2.0 linked data with
Library of Congress id.loc.gov linked-data webservices"""
__author__ = "Jeremy Nelson, Mike Stabile"

import datetime
import sys
import unicodedata
import urllib.parse

import bibcat
import requests
import rdflib

from fuzzywuzzy import fuzz
from bibcat.linkers.linker import Linker

#! PREFIX should be generated from RDF Framework in the future
PREFIX = """PREFIX bf: <http://id.loc.gov/ontologies/bibframe/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>"""

#! BF should be from the RDF Framework Namespace manager
BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")

class LibraryOfCongressLinker(Linker):
    """Library of Congress Linked Data Linker"""
    ID_LOC_URL = "http://id.loc.gov/search/"

    def __init__(self, **kwargs):
        super(LibraryOfCongressLinker, self).__init__(**kwargs)
        self.cutoff = kwargs.get("cutoff", 90)
        self.graph = kwargs.get("graph", None)
        self.punct_map = dict.fromkeys(i for i in range(sys.maxunicode)
                                       if unicodedata.category(chr(i)).startswith('P'))


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
                return
            for entity in self.graph.subjects(predicate=BF.subject,
                                              object=subject_iri):
                self.graph.add((entity, BF.subject, lsch_iri))
            self.graph.add((lsch_iri, rdflib.RDF.type, BF.Topic))
            self.graph.add((lsch_iri,
                            rdflib.RDFS.label,
                            rdflib.Literal(title)))
            bibcat.delete_iri(subject_iri, self.graph)

    def __process_loc_results__(self, results, label):
        title, loc_uri, term_weights = None, None, dict()
        for row in results:
            if isinstance(row, dict):
                continue
            if row[0].startswith('atom:entry'):
                if row[2][0].startswith("atom:title"):
                    title = row[2][-1]
                
                #if fuzz.ratio(label, title) < self.cutoff:
                #    continue
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

    def link_lc_subjects(self, subject_iri, raw_label):
        """Method takes a subject IRI and a label, first does a split on
        -- character which is commonly used to delimit complex LCSH

        Args:
            subject_iri(rdflib.URIRef): Subject IRI
            label(str): Subject IRI's RDFS Label or RDF Value
        """
        terms = raw_label.split("--")
        if len(terms) < 1:
            return
        elif len(terms) == 1:
            self.__link_subject__(terms[0], subject_iri)


    def run(self, graph=None):
        """Runs linker on existing bf:subject Blank Nodes"""
        if graph is not None:
            self.graph = graph
            result = self.graph.query(SELECT_SUBJECTS)
            bindings = result.bindings
        start = datetime.datetime.utcnow()
        print("Starting LCSH Linker Service at {}, total to process {}".format(
            start,
            len(bindings)))
        for i, row in enumerate(bindings):
            subject_iri = row.get('subject')
            label = row.get('label')
            self.link_lc_subjects(subject_iri, label)
            if not i%10 and i > 0:
                print(".", end="")
            if not i%100:
                print(i, end="")
        end = datetime.datetime.utcnow()
        print("Finished LCSH Linker Service at {}, total time={} mins".format(
            end,
            (end-start).seconds /60.0))


SELECT_SUBJECTS = PREFIX + """

SELECT DISTINCT ?subject ?label
WHERE {
	?subject rdf:type bf:Topic ;
	         rdfs:label ?label .
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
