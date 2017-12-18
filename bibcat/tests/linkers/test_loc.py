import rdflib
import unittest
import bibcat.linkers.loc as loc

__author__ = "Jeremy Nelson"

BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")
SKOS = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")

class TestLibraryOfCongressLinker(unittest.TestCase):

    def setUp(self):
        pass

    def test_init(self):
        default_linker = loc.LibraryOfCongressLinker()
        self.assertEqual(default_linker.triplestore_url,
                         "http://localhost:9999/blazegraph/sparql")
        self.assertIsNone(default_linker.graph)
        self.assertEqual(default_linker.cutoff, 90)
        self.assertEqual(loc.LibraryOfCongressLinker.ID_LOC_URL,
            "http://id.loc.gov/search/")
        self.assertEqual(default_linker.base_url,
                         'http://bibcat.org/')

class TestLibraryOfCongressLinker_link_lc_subjects(unittest.TestCase):

    def setUp(self):
        self.graph = rdflib.Graph()
        self.entity = rdflib.URIRef("http://bibcat.org/Entity1234")
        self.graph.add((self.entity, rdflib.RDF.type, BF.Work))
        self.bf_topic_iri = rdflib.URIRef("http://bibcat.org/Topic650-34")
        self.graph.add((self.bf_topic_iri, rdflib.RDF.type, BF.Topic))
        self.graph.add((self.entity, BF.subject, self.bf_topic_iri))
        self.linker = loc.LibraryOfCongressLinker(graph=self.graph)

    def test_link_lc_subjects_not_found(self):
        label = rdflib.Literal("GaRarandom334Chars")
        self.graph.add((self.bf_topic_iri, rdflib.RDFS.label, label))
        self.assertEqual(len(self.graph), 4)
        self.linker.link_lc_subjects(self.bf_topic_iri, str(label))
        self.assertEqual(len(self.graph), 4)
        extracted_iri = self.graph.value(predicate=rdflib.RDF.type,
                                         object=BF.Topic)
        self.assertEqual(extracted_iri, self.bf_topic_iri)

    def test_link_lc_subjects_single_term(self):
        label = rdflib.Literal("Green")
        self.graph.add((self.bf_topic_iri, rdflib.RDFS.label, label))
        self.linker.link_lc_subjects(self.bf_topic_iri, str(label))
        extracted_iri = self.graph.value(predicate=rdflib.RDF.type,
                                         object=BF.Topic)
        self.assertEqual(
            extracted_iri, 
            rdflib.URIRef("http://id.loc.gov/authorities/subjects/sh85057206"))

    def test_link_lc_subjects_multiple_words(self):
        label = rdflib.Literal("Electronic books.")
        self.graph.add((self.bf_topic_iri, rdflib.RDFS.label, label))
        self.linker.link_lc_subjects(self.bf_topic_iri, str(label))
        extracted_iri = self.graph.value(predicate=rdflib.RDF.type,
                                         object=BF.Topic)
        self.assertEqual(
            extracted_iri,
            rdflib.URIRef("http://id.loc.gov/authorities/subjects/sh93007047"))

   

class TestLibraryOfCongressLinker_link_lc_subjects_OrderedCollection(unittest.TestCase):

    def setUp(self):
        self.graph = rdflib.Graph()
        self.graph.namespace_manager.bind("skos", SKOS)
        self.graph.namespace_manager.bind("bf", BF)
        self.entity = rdflib.URIRef("http://bibcat.org/Work/1234")
        self.graph.add((self.entity, rdflib.RDF.type, BF.Work))
        self.bf_topic_iri = rdflib.URIRef("http://bibcat.org/Topic345")
        self.graph.add((self.entity, BF.subject, self.bf_topic_iri))
        self.graph.add((self.bf_topic_iri, rdflib.RDF.type, BF.Topic))
        self.graph.add((self.bf_topic_iri, 
                        rdflib.RDF.value, 
                        rdflib.Literal("Green--Electronic Books")))
        self.linker = loc.LibraryOfCongressLinker(graph=self.graph, 
            base_url='http://bibcat.org/')

    def test_existing_is_ordered_collection(self):
        self.linker.link_lc_subjects(self.bf_topic_iri, "Green--Electronic Books")
        existing_classes = sorted([s for s in self.graph.objects(subject=self.bf_topic_iri,
                                                            predicate=rdflib.RDF.type)])
        self.assertListEqual(existing_classes,
                             [BF.Topic, SKOS.OrderedCollection])

    def test_existing_loc_iri_in_order(self):
        self.graph.remove((self.bf_topic_iri, rdflib.RDF.value, rdflib.Literal("Green--Electronic Books")))
        self.graph.add((self.bf_topic_iri, 
                        rdflib.RDF.value,
                        rdflib.Literal("Advertising--Alcoholic beverages--Government policy")))
        self.linker.link_lc_subjects(self.bf_topic_iri, 
                                     "Advertising--Alcoholic beverages--Government policy")

        sparql = """prefix bf: <http://id.loc.gov/ontologies/bibframe/>
prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> 
prefix skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT ?loc_iri
        WHERE {
            <http://bibcat.org/Topic345> skos:memberList/rdf:rest*/rdf:first ?loc_iri 
        }"""
        result = self.graph.query(sparql)
        loc_iris = [r.get('loc_iri') for r in result.bindings]
        self.assertListEqual(
            loc_iris,
            [rdflib.URIRef('http://id.loc.gov/authorities/subjects/sh85001086'),
             rdflib.term.URIRef('http://bibcat.org/topic/alcoholic-beverages'),
             rdflib.term.URIRef('http://bibcat.org/topic/government-policy')])
             #rdflib.URIRef('http://id.loc.gov/authorities/subjects/sh85003283'),
             #rdflib.URIRef('http://id.loc.gov/authorities/subjects/sh99005269')])

        
        
        
class TestLibraryOfCongressSRULinker(unittest.TestCase):

    def setUp(self):
        pass

    def test_default_init(self):
        default_linker = loc.LibraryOfCongressSRULinker()
        self.assertEqual(default_linker.triplestore_url,
                         "http://localhost:9999/blazegraph/sparql")
        self.assertIsNone(default_linker.graph)
        self.assertEqual(default_linker.cutoff, 90)
        self.assertEqual(loc.LibraryOfCongressSRULinker.NAF_SRU,
                         "http://lx2.loc.gov:210/NAF?")
        self.assertEqual(loc.LibraryOfCongressSRULinker.SAF_SRU,
                         "http://lx2.loc.gov:210/SAF?")
        self.assertEqual(default_linker.base_url,
                         'http://bibcat.org/')


class TestLibraryOfCongressSRULinker_link_lc_subjects(unittest.TestCase):

    def setUp(self):
        self.graph = rdflib.Graph()
        self.test_entity = rdflib.URIRef("http://bibcat.org/test-entity")
        self.linker = loc.LibraryOfCongressSRULinker()
        
    def test_link_lc_subjects(self):
        self.linker.link_lc_subjects(self.test_entity, "Green")
            
if __name__ == "__main__":
    unittest.main()
