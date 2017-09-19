import rdflib
import unittest
from bibcat import clean_uris, create_rdf_list, delete_bnode, delete_iri
from bibcat import modified_bf_desc, slugify, wikify, replace_iri 

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


class Test_delete_bnode(unittest.TestCase):

    def setUp(self):
        self.graph = rdflib.Graph()
        self.entity = rdflib.URIRef("https://bibcat.org/test-entity")
        self.simple_title_bnode = rdflib.BNode()
        self.graph.add((self.entity,
                        rdflib.RDF.type,
                        BF.Title))
        self.graph.add((self.entity, BF.title, self.simple_title_bnode))
        self.graph.add((self.simple_title_bnode, 
                        BF.mainTitle, 
                        rdflib.Literal("This is a test")))
        self.top_title_bnode = rdflib.BNode()
        self.graph.add((self.entity, BF.title, self.top_title_bnode))
        secondary_title_bnode = rdflib.BNode()
        self.graph.add((self.top_title_bnode, rdflib.RDF.type, BF.Topic))
        self.graph.add((self.top_title_bnode, 
                        rdflib.RDFS.label, 
                        rdflib.Literal("This is a title and a name")))
        self.graph.add((self.top_title_bnode, SCHEMA.name, secondary_title_bnode))
        self.graph.add((secondary_title_bnode, 
                        rdflib.RDF.value,
                        rdflib.Literal("This is a name")))

    def test_delete_1_level_deep_bnode(self):
        start_size = len(self.graph)
        delete_bnode(self.graph, self.simple_title_bnode)
        finish_size = len(self.graph)
        self.assertEqual(start_size-finish_size, 2)
        self.assertIsNone(self.graph.value(subject=self.simple_title_bnode,
                                           predicate=BF.mainTitle))

    def test_delete_2_level_deep_bnode(self):
        start_size = len(self.graph)
        delete_bnode(self.graph, self.top_title_bnode)
        finish_size = len(self.graph)
        self.assertEqual(start_size-finish_size, 5)
        self.assertIsNone(self.graph.value(subject=self.top_title_bnode,
                                           predicate=rdflib.RDFS.label))

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
        self.entity_two = rdflib.URIRef("https://bibcat.org/test-entity-two")
        self.graph.add((self.entity_two, 
                        rdflib.RDF.type, 
                        rdflib.RDFS.Resource))
        self.graph.add((self.entity_two, 
                        rdflib.RDFS.label, 
                        rdflib.Literal("Test Entity Two", lang="en")))
        title_bnode = rdflib.BNode()
        self.graph.add((self.entity_two, BF.title, title_bnode))
        self.graph.add((title_bnode, rdflib.RDF.type, BF.Title))
        self.graph.add((title_bnode, BF.subTitle, rdflib.Literal("Subtitle ")))


    def test_delete_iri(self):
        start_size = len(self.graph)
        delete_iri(self.graph, self.entity_one)
        finish_size = len(self.graph)
        self.assertEqual(start_size - finish_size, 2)
        self.assertIsNone(self.graph.value(subject=self.entity_one,
                                           predicate=rdflib.RDF.type))

    def test_delete_complex_iri(self):
        start_size = len(self.graph)
        delete_iri(self.graph, self.entity_two)
        finish_size = len(self.graph)
        self.assertEqual(start_size-finish_size, 5)
        self.assertIsNone(self.graph.value(subject=self.entity_two,
                                           predicate=rdflib.RDF.type))
 
class Test_modified_bf_desc(unittest.TestCase):

    def setUp(self):
        self.graph = rdflib.Graph()
        self.graph.namespace_manager.bind("bf", BF)
        self.entity_iri = rdflib.URIRef("https://bibcat.org/test-entity")
        self.graph.add((self.entity_iri, 
                        rdflib.RDF.type, 
                        rdflib.RDFS.Resource))
        self.graph.add((self.entity_iri, 
                        rdflib.RDFS.label, 
                        rdflib.Literal("Test Entity One", lang="en")))
        self.message = "Changed rdfs:label"
        

    def test_default(self):
        modified_bf_desc(graph=self.graph,
                         entity_iri=self.entity_iri,
                         msg=self.message)
        admin_meta_bnode = self.graph.value(
            subject=self.entity_iri,
            predicate=BF.adminMetadata)
        self.assertIsNotNone(admin_meta_bnode)
        msg_value = self.graph.value(
            subject=admin_meta_bnode,
            predicate=rdflib.RDF.value)
        self.assertEqual(str(msg_value), self.message)
            
    def test_missing_all_keywords(self):
        self.assertRaises(AttributeError,
                          modified_bf_desc)

    def test_missing_graph_keyword(self):
        self.assertRaises(AttributeError,
                          modified_bf_desc,
                          entity_iri=self.entity_iri,
                          msg=self.message)        

    def test_missing_entity_iri_keyword(self):
        self.assertRaises(AssertionError,
                          modified_bf_desc,
                          graph=self.graph,
                          msg=self.message)

    def test_missing_msg_keyword(self):
        self.assertRaises(AttributeError,
                          modified_bf_desc,
                          graph=self.graph,
                          entity_iri=self.entity_iri)

    def test_agent_iri(self):
        agent_iri = rdflib.URIRef("https://bibcat.org/Agent-1")
        self.graph.add((agent_iri, rdflib.RDF.type, BF.Agent))
        modified_bf_desc(graph=self.graph,
                         entity_iri=self.entity_iri,
                         msg=self.message,
                         agent_iri=agent_iri)
        admin_bnode = self.graph.value(subject=self.entity_iri,
                                       predicate=BF.adminMetadata)
        self.assertIsNotNone(admin_bnode)
        desc_modifier = self.graph.value(subject=admin_bnode,
                                         predicate=BF.descriptionModifier)
        self.assertEqual(agent_iri, desc_modifier)

    def test_person_iri(self):
        person_iri = rdflib.URIRef("https://bibcat.org/Person-1")
        self.graph.add((person_iri, rdflib.RDF.type, BF.Person))
        modified_bf_desc(graph=self.graph,
                         entity_iri=self.entity_iri,
                         msg=self.message,
                         agent_iri=person_iri)
        admin_bnode = self.graph.value(subject=self.entity_iri,
                                       predicate=BF.adminMetadata)
        self.assertIsNotNone(admin_bnode)
        desc_modifier = self.graph.value(subject=admin_bnode,
                                         predicate=BF.descriptionModifier)
        self.assertEqual(person_iri, desc_modifier)

       

    def test_org_iri(self):
        org_iri = rdflib.URIRef("https://bibcat.org/Organization-1")
        self.graph.add((org_iri, rdflib.RDF.type, BF.Person))
        modified_bf_desc(graph=self.graph,
                         entity_iri=self.entity_iri,
                         msg=self.message,
                         agent_iri=org_iri)
        admin_bnode = self.graph.value(subject=self.entity_iri,
                                       predicate=BF.adminMetadata)
        self.assertIsNotNone(admin_bnode)
        desc_modifier = self.graph.value(subject=admin_bnode,
                                         predicate=BF.descriptionModifier)
        self.assertEqual(org_iri, desc_modifier)

                     
                

    def tearDown(self):
        pass 

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
