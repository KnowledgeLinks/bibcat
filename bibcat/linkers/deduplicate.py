"""Deduplicator class attempts a simple comparison of values and labels of
target RDF classes on the input RDF graph, generates new IRIs in the triplestore
"""

from types import SimpleNamespace
import rdflib
import requests

from bibcat import replace_iri, slugify
try:
    import instance.config as config
except ImportError:
    config = SimpleNamespace()
    config.TRIPLESTORE_URL = "http://localhost:9999/blazegraph/sparql"

__author__ = "Jeremy Nelson"


class Deduplicator(object):
    """Class de-duplicates and generates IRIs"""

    def __init__(self, **kwargs):
        self.triplestore_url = kwargs.get(
            'triplestore_url',
            config.TRIPLESTORE_URL)
        self.output = None
        self.default_classes = kwargs.get("classes", [])
        self.subject_pattern = kwargs.get("subject_pattern",
            "{base_url}{class_name}/{label}")

    def __get_or_mint__(self, old_iri, iri_class, label):
        """Attempts to retrieve any existing IRIs that match the label
        if not found, mints a new IRI. Returns an existing or new
        entity IRI

        Args:

        -----
            old_iri: rdflib.URIRef IRI 
            iri_class: rdflib.URIRef predicate IRI
            label: string of rdflib.Literal for the RDFS label
        """
        sparql = """prefix bf: <http://id.loc.gov/ontologies/bibframe/>
        prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?entity ?label
        WHERE {{
            ?entity rdf:type <{0}> ;
            OPTIONAL {{ ?entity rdfs:label ?label . }}
            OPTIONAL {{ ?entity rdf:value ?label . }}
            FILTER(CONTAINS(?label, \"""{1}\"""))
        }}""".format(iri_class, label)
        result = requests.post(self.triplestore_url,
            data={"query": sparql,
                  "format": "json"})
        #import pdb; pdb.set_trace()
        if result.status_code > 399:
            return
        bindings = result.json().get('results').get('bindings')
        if len(bindings) > 0:
            # Use first binding
            entity_iri = rdflib.URIRef(bindings[0].get('entity').get('value'))
            existing_label = rdflib.Literal(bindings[0].get('label').get('value'))
            if existing_label != label:
                # Add label as an skos:altLabel
                self.output.add((entity_iri, 
                                 processor.NS_MGR.skos.altLabel, 
                                 label))
        else:
            class_name = str(iri_class).split("/")[-1].lower()
            # Mint new IRI based on class and slugged label
            new_url = self.subject_pattern.format(
                base_url=config.BASE_URL,
                class_name=class_name,
                label=slugify(label))
            entity_iri = rdflib.URIRef(new_url)
            self.output.add((entity_iri, rdflib.RDFS.label, label))
        replace_iri(self.output, old_iri, entity_iri)
        # Add old iri as owl:sameAs to entity_iri
        if isinstance(old_iri, rdflib.URIRef):
            self.output.add((entity_iri, 
                             rdflib.OWL.sameAs,
                             old_iri))
        return entity_iri


    def run(self, input_graph, rdf_classes=[]):
        """Takes a graph and deduplicates various RDF classes

        Args:

        -----
            graph: rdflib.Graph or rdflib.ConjunctiveGraph
            rdf_classes: list of RDF Classes to use in filtering
                         IRIs
        """
        self.output = input_graph
        all_classes = self.default_classes + rdf_classes
        for class_ in all_classes:
            for entity in self.output.subjects(
                    predicate=rdflib.RDF.type,
                    object=class_):
                label = self.output.value(subject=entity,
                                          predicate=rdflib.RDFS.label)
                if label is None:
                    continue
                self.__get_or_mint__(entity, class_, label)

