import rdflib
import unittest
from bibcat import delete_iri, replace_iri, slugify, wikify

__author__ = "Jeremy Nelson"

class Test_delete_iri(unittest.TestCase):

    def setUp(self):
        self.graph = rdflib.Graph()
        self.entity_one = rdflib.URIRef("https://bibcat.org/test-entity")
        self.graph.add((self.entity_one, 
                        rdflib.RDF.type, 
                        rdflib.RDFS.Resource))
        self.graph.add((self.entity_one, 
                        rdflib.RDFS.label, 
                        rdflib.Literal("Test Entity One", lang="en")))

    def test_delete_iri(self):
        self.assertEqual(len(self.graph), 2)
        delete_iri(self.entity_one, self.graph)
        self.assertEqual(len(self.graph), 0)

class Test_replace_iri(unittest.TestCase):
    
    def setUp(self):
        self.graph = rdflib.Graph()
        self.entity_one = rdflib.URIRef("https://bibcat.org/test-entity")
        self.graph.add((self.entity_one, 
                        rdflib.RDF.type, 
                        rdflib.RDFS.Resource))
        self.graph.add((self.entity_one, 
                        rdflib.RDFS.label, 
                        rdflib.Literal("Test Entity One", lang="en")))

    def test_simple_replace(self):
        new_iri = rdflib.URIRef("https://bibcat.org/replace-entity")
        replace_iri(self.graph, self.entity_one, new_iri)
        self.assertEqual(self.graph.value(subject=new_iri, 
                                          predicate=rdflib.RDF.type),
                         rdflib.RDFS.Resource)
        self.assertEqual(self.graph.value(subject=new_iri,
                                          predicate=rdflib.RDFS.label),
                         rdflib.Literal("Test Entity One", lang="en"))
        self.assertIsNone(self.graph.value(subject=self.entity_one,
                                           predicate=rdflib.RDF.type))

    def test_bnode_old_iri_exception(self):
        pass


class Test_slugify(unittest.TestCase):

    def setUp(self):
        pass

    def test_simple_name(self):
        self.assertEqual("mexico-city",
            slugify("Mexico City"))


class Test_wikify(unittest.TestCase):

    def setUp(self):
        pass

    def test_simple_name(self):
        self.assertEqual("Tokyo_Japan",
            wikify("Tokyo, Japan"))

    def tearDown(self):
        pass


if __name__ == '__main__':
    unittest.main()
