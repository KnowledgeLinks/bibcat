import rdflib
import unittest
from bibcat import clean_uris, create_rdf_list, delete_iri, replace_iri 
from bibcat import slugify, wikify

__author__ = "Jeremy Nelson"

BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")
SCHEMA = rdflib.Namespace("http://schema.org/")

class Test_clean_uris(unittest.TestCase):

    def setUp(self):
        self.graph = rdflib.Graph()

    def test_good_uri(self):
        entity_1 = rdflib.URIRef("https://bibcat.org/test-entity")
        self.graph.add((entity_1, rdflib.RDF.type, rdflib.RDFS.Resource))
        clean_uris(self.graph)
        extracted_entity = self.graph.value(predicate=rdflib.RDF.type,
                                            object=rdflib.RDFS.Resource)
        self.assertEqual(entity_1, extracted_entity)


class Test_create_rdf_list(unittest.TestCase):

    def setUp(self):
        self.graph = rdflib.Graph()
        self.entity = rdflib.URIRef("https://bibcat.org/test-entity")
        self.literal_list = [rdflib.Literal("One", lang="en"), 
                             rdflib.Literal("Dos", lang="es"), 
                             rdflib.Literal("San", lang="jp")]


    def test_rdf_list_size_one(self):
        self.graph.add((self.entity, 
                        rdflib.RDF.type, 
                        create_rdf_list(self.graph, [rdflib.RDFS.Resource,])))
        self.assertEqual(len(self.graph), 3)

    def test_rdf_list_size_three(self):
        self.graph.add((self.entity, 
                        SCHEMA.numbers,
                        create_rdf_list(self.graph, self.literal_list)))
        count_sparql = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>  
            SELECT (COUNT(?a) AS ?count) 
            WHERE {?a rdf:first+ ?c}"""
        result = self.graph.query(count_sparql)
        self.assertEqual(int(result.bindings[0].get('count')),
                         3)

    def test_rdf_list_size_three_order_2(self):
        self.graph.add((self.entity,
                        SCHEMA.numbers,
                        create_rdf_list(self.graph, self.literal_list)))
        second_node_sparql = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX schema: <http://schema.org/>
            SELECT ?item
            WHERE {
                <https://bibcat.org/test-entity> schema:numbers/rdf:rest/rdf:rest/rdf:first ?item
            }"""
        result = self.graph.query(second_node_sparql)
        self.assertEqual(result.bindings[0].get('item'), 
                         self.literal_list[2])


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
        delete_iri(self.graph, self.entity_one)
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
