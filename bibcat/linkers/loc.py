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
ID_LOC_URL = "http://id.loc.gov/search/"


def link_term(term, number=1):
    """Quick function takes a term and look-ups on LOC search {}

    Args:
        term(str): String term
        number(int): Number of results to return
    """.format(ID_LOC_URL)
    output = []
    term_weights = dict()
    params = {"q": term,
              "format": "json"}
    loc_url = "{}?{}".format(
        ID_LOC_URL, 
        urllib.parse.urlencode(params))
    result = requests.get(loc_url)
    results = result.json()
    for row in results:
        if isinstance(row, dict) or not row[0].startswith('atom:entry'):
            continue
        if row[2][0].startswith("atom:title"):
            title = row[2][-1]
        if row[3][0].startswith("atom:link"):
            loc_url = row[3][-1].get('href')
            if "subjects/" in loc_url:
                bf_class = BF.Topic
            elif "organizations/" in loc_url:
                bf_class = BF.Organization
            else:
                 bf_class = BF.Agent
            loc_uri = rdflib.URIRef(loc_url)
            term_weights[str(loc_uri)] = {
                     "weight": fuzz.ratio(term, title),
                     "class": bf_class,
                     "title": title}
    results = sorted(term_weights.items(), key=lambda x: x[1]['weight'])
    results.reverse()
    for i,row in enumerate(results[0:number]):
        loc_url = row[0]
        title = row[1].get('title')
        output.append({"iri": rdflib.URIRef(loc_url), 
                       "title": rdflib.Literal(title)})
    return output

class LibraryOfCongressLinker(Linker):
    """Library of Congress Linked Data Linker"""
    ID_LOC_URL = "http://id.loc.gov/search/"

    def __init__(self, **kwargs):
        super(LibraryOfCongressLinker, self).__init__(**kwargs)
        self.base_url = kwargs.get('base_url', 'http://bibcat.org/')
        self.cutoff = kwargs.get("cutoff", 90)
        self.graph = kwargs.get("graph", None)
        self.punct_map = dict.fromkeys(i for i in range(sys.maxunicode)
                                       if unicodedata.category(chr(i)).startswith('P'))
        self.subject_sparql = kwargs.get("subject_sparql", SELECT_BF_SUBJECTS)

    def __build_lc_url__(self, term, schema_iri):
        """Builds and returns results of calling LOC search services
        
        Args:
                  term(str): String term to search on
            schema_iri(str): URL of what schema to use
        """
        lc_search_url = LibraryOfCongressLinker.ID_LOC_URL
        label = term.translate(self.punct_map)
        lc_search_url += "?" + urllib.parse.urlencode(
            {"q": label,
             "format": "json"})
        #lc_search_url += "&q=scheme:{}".format(schema_iri)
        loc_result = requests.get(lc_search_url)
        if loc_result.status_code > 399:
            raise ValueError(
                "Cannot run, HTTP error {}\n{}".format(
                    subject_result.status_code,
                    subject_result.text))
        return loc_result

    def __link_entity__(self, entity):
        label = self.graph.value(subject=entity,
                                 predicate=rdflib.RDFS.label)
        if label is None:
            label = self.graph.value(subject=entity,
                                     predicate=rdflib.RDF.value)
            if label is None:
                return
        loc_url = "{}?{}".format(
            LibraryOfCongressLinker.ID_LOC_URL,
            urllib.parse.urlencode({"q": label,
                                    "format": "json"}))
        result = requests.get(loc_url)
        loc_iri, label = self.__process_loc_results__(
            result.json(),
            label)
        

    def __link_names__(self, name, name_iri):
        """Function takes a name and queries LOC service
        Args:
            name(str): Name phrase
            name_iri(rdflib.URIRef): Internal name IRI or blank node
        """
        name_result = self.__build_lc_url__(
            name,
            "http://id.loc.gov/authorities/name")
        loc_naf_iri, label = self.__process_loc_results__(
            name_result.json(),
            name)
        
        if loc_naf_iri is not None:
            bibcat.replace_iri(self.graph, name_iri, loc_naf_iri)
        

    def __link_subject__(self, term, subject_iri):
        """Function takes a term and queries LOC service
        Args:
            term(str): Term
            subject_iri(rdflib.URIRef): Subject IRI
        """
        subject_result = self.__build_lc_url__(
            term, 
            "http://id.loc.gov/authorities/subjects")
        lsch_iri, title = self.__process_loc_results__(
            subject_result.json(),
            term)
        if lsch_iri is None:
            return None, None
        entities = []
        for row in self.graph.subjects(predicate=BF.subject,
                                       object=subject_iri):
            entities.append(row)
        for entity in entities:
            self.graph.add((entity, BF.subject, lsch_iri))
            bibcat.delete_iri(self.graph, subject_iri)
            return lsch_iri, title
        return None, None

    def __process_loc_results__(self, results, label):
        """Method takes the json results from running the 

        Args:
            results(list): List of JSON rows from LOC ID call
            label(str): Original Label
        """
        title, loc_uri, term_weights = None, None, dict()
        for row in results:
            if isinstance(row, dict) or not row[0].startswith('atom:entry'):
                continue
            if row[2][0].startswith("atom:title"):
                title = row[2][-1]
            if row[3][0].startswith("atom:link"):
                loc_url = row[3][-1].get('href')
                if "subjects/" in loc_url:
                    bf_class = BF.Topic
                elif "organizations/" in loc_url:
                    bf_class = BF.Organization
                else:
                    bf_class = BF.Agent
                loc_uri = rdflib.URIRef(loc_url)
                term_weights[str(loc_uri)] = {
                        "weight": fuzz.ratio(label, title),
                        "class": bf_class,
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
        entities = [entity for entity in self.graph.subjects(
                                             predicate=BF.subject,
                                             object=topic_subject)]
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
                topic_bnode = topic_subject
                # Create a new topic_subject as an IRI
                topic_subject = rdflib.URIRef("{}topic/{}".format(
                    self.base_url,
                    bibcat.slugify(raw_label)))
                for entity in entities:
                    self.graph.add((entity, BF.subject, topic_subject))
                bibcat.delete_bnode(self.graph, topic_bnode)
            # Add topic_subject back as a bf:Topic and SKOS.OrganizedCollection
            self.graph.add((topic_subject, rdflib.RDF.type, BF.Topic))
            self.graph.add((topic_subject, 
                            rdflib.RDF.type, 
                            SKOS.OrderedCollection))
            self.graph.add((topic_subject, 
                            rdflib.RDFS.label, 
                            rdflib.Literal(raw_label)))
            if not self.graph.value(subject=topic_subject, 
                                    predicate=SKOS.memberList):
                self.graph.add((topic_subject,
                                SKOS.memberList,
                                bibcat.create_rdf_list(self.graph,
                                                       rdf_list)))

    def run(self, graph=None):
        if graph is not None:
            self.graph = graph
        counter = 0
        start = datetime.datetime.utcnow()
        print("Starting LCSH Linker Service at {}".format(start))
        for class_ in [BF.Agent, BF.Person, BF.Organization]:
            for entity in self.graph.subjects(
                predicate=rdflib.RDF.type,
                object=class_):
                if not counter%10 and counter > 0:
                    print(".", end="")
                if not counter%100:
                    print("{:,}".format(counter), end="")
                counter += 1
                label = self.graph.value(subject=entity, 
                    predicate=rdflib.RDFS.label)
                if label is None:
                    label = self.graph.value(subject=entity,
                                predicate=rdflib.RDF.label)
                if label is None:
                    continue
                
                self.__link_names__(str(label), entity)
        # Running Subject
        result = self.graph.query(self.subject_sparql)
        for row in result.bindings:
            subject_iri = row.get('subject')
            label = row.get('label')
            self.link_lc_subjects(subject_iri, label)
            if not counter%10 and counter > 0:
                print(".", end="")
            if not counter%100:
                print("{:,}".format(counter), end="")
            counter += 1
        end = datetime.datetime.utcnow()
        print("""Finished LCSH Linker Service at {}, 
total time={} mins
Total subjects checked {:,}""".format(
            end,
            (end-start).seconds /60.0,
            counter))


    def old_run(self, graph=None):
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


class LibraryOfCongressSRULinker(Linker):
    """Uses Library of Congress SRU <http://www.loc.gov/standards/sru/> for Names and
    Subject Authorities."""
    NAF_SRU = "http://lx2.loc.gov:210/NAF?"
    SAF_SRU = "http://lx2.loc.gov:210/SAF?"

    def __init__(self, **kwargs):
        super(LibraryOfCongressSRULinker, self).__init__(**kwargs)
        self.base_url = kwargs.get('base_url', 'http://bibcat.org/')
        self.cutoff = kwargs.get("cutoff", 90)
        self.graph = kwargs.get("graph", None)
        self.punct_map = dict.fromkeys(i for i in range(sys.maxunicode)
                                       if unicodedata.category(chr(i)).startswith('P'))
        self.subject_sparql = kwargs.get("subject_sparql", SELECT_BF_SUBJECTS)


    def link_lc_names(self, entity, label):
        """Searches LOC Name authority

        :args:
            enity_iri(rdflib.URIRef|rdflib.BNode): Entity IRI or Blank Node
        """
        sru_url = LibraryOfCongressSRULinker.NAF_SRU
        sru_url += urllib.parse.urlencode({"operation": "searchRetrieve",
                                           "version": 1.1,
                                           "personalName": label,
                                           "maximumRecords": 10,
                                           "recordSchema": "dc"})
        result = requests.get(sru_url)


    def link_lc_subjects(self, entity, label):
        """Searches LCSH for a match on the entity_iri

        :args:
            entity_iri(rdflib.URIRef|rdflib.BNode): Entity IRI or Blank Node
            label(str): String to search on
        """
        sru_url = LibraryOfCongressSRULinker.SAF_SRU 
        sru_url += urllib.parse.urlencode({"operation": "searchRetrieve",
                                           "version": 1.1,
                                           "maximumRecords": 10,
                                           "recordSchema": "dc"})
        sru_url += "&query=" + urllib.parse.urlencode(
            {"bath.topicalSubject": label})
        result = requests.get(sru_url)

    def run(self, graph=None):
        """Runs LOC Linker Service using SRU

        :args: 
            graph(rdflib.Graph): Input graph
        """
        if graph is not None:
            self.graph = graph
        for entity_iri, label in self.graph.query(SELECT_BF_AGENTS):
            self.link_lc_names(entity_iri, label)
        for entity_iri, label in self.graph.query(SELECT_BF_SUBJECTS):
            self.link_lc_subjects(entity_iri, label)

FIND_SUBJECT_OF_NAMES = PREFIX + """

SELECT DISTINCT ?subject

WHERE {{
    ?subject bf:contribution ?contrib .
    OPTIONAL {{ ?contrib ?predicate <{instance}> . }}
    OPTIONAL {{ ?contrib ?predicate _:{bnode} . }}
    
}} ORDER BY ?label"""

SELECT_BF_AGENTS = PREFIX + """

SELECT DISTINCT ?agent ?label
WHERE {
    OPTIONAL { ?agent rdf:type bf:Agent }
    OPTIONAL { ?agent rdf:type bf:Person }
    OPTIONAL { ?agent rdf:type bf:Organization }
    ?agent rdfs:label ?label .

} ORDER BY ?agent"""



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
