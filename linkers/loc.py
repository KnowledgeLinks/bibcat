"""Helper Class and Functions for linking BIBFRAME 2.0 linked data with 
Library of Congress id.loc.gov linked-data webservices"""
__author__ = "Jeremy Nelson, Mike Stabile"

import datetime
import os
import requests
import rdflib
try:
    from ..ingesters.ingester import new_graph, NS_MGR
    from .linker import BIBCAT_BASE, Linker, LinkerError
except ValueError:
    from ingesters.ingester import new_graph, NS_MGR
    from linkers.linker import BIBCAT_BASE, Linker, LinkerError


from fuzzywuzzy import fuzz

LCSH_GRAPH = new_graph()
LCSH_GRAPH.parse(os.path.join(BIBCAT_BASE, "rdf-references/loc_subjects.ttl"),
                 format='turtle')

class LibraryOfCongressLinker(Linker):
    """Library of Congress Linked Data Linker"""
    ID_LOC_URL = "http://id.loc.gov/"

    def __init__(self, **kwargs):
        super(LibraryOfCongressLinker, self).__init__(**kwargs)


    def __link_lcsh__(self, instance_uri, label, cutoff=90):
        """Attempts to match incoming bnode subject label to LCSH iri"""
        for row in LCSH_GRAPH.query(FIND_LCSH.format(label)):
            subject_uri, subject_label = row
            if fuzz.ratio(subject_label, label) >= cutoff:
                update_sparql = UPDATE_SUBJECT.format(
                                    subject_uri,
                                    instance_uri, 
                                    label)
                result = requests.post(self.triplestore_url,
                            data=update_sparql,
                            headers={"Content-Type": "application/sparql-update"})
                if result.status_code > 399:
                    raise LinkerError(
                        "Failed bf:subject with LCSH iri http error code={}".format(
                            result.status_code,
                            result.text))
       

    def run(self):
        """Runs linker on existing bf:subject Blank Nodes"""
        result = requests.post(self.triplestore_url,
            data={"query": SUBJECT_BNODES,
                  "format": "json"})
        if result.status_code > 399:
            raise LinkerError("Failed to run SUBJECT_BNODES sparql query {}".format(
                    result.status_code),
                result.text)
        bindings = result.json().get('results').get('bindings')
        start = datetime.datetime.utcnow()
        print("Starting LCSH Linker Service at {}, total to process {}".format(
            start,
            len(bindings)))
        for i,row in enumerate(bindings):
            instance_uri = row.get('instance').get('value')
            label = row.get('label').get('value')
            self.__link_lcsh__(instance_uri, label)
            if not i%10 and i > 0:
                print(".", end="")
            if not i%100:
                print(i, end="")
        end = datetime.datetime.utcnow()
        print("Finished LCSH Linker Service at {}, total time={} mins".format(
            end,
            (end-start).seconds /60.0))

FIND_LCSH = Linker.NS.prefix() + """

SELECT ?subject_uri ?label 
WHERE {{
    ?subject_uri bf:subject ?bnode .
    ?bnode rdf:value ?label .
    FILTER(CONTAINS(?label, "{0}"))
}}"""

SUBJECT_BNODES = Linker.NS.prefix() + """

SELECT ?instance ?label 
WHERE {
    ?instance bf:subject ?subject .
    ?subject rdf:value ?label .
    filter(isblank(?subject))
}"""

UPDATE_SUBJECT = Linker.NS.prefix() + """

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
