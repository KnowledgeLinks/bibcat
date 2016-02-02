__author__ = "Jeremy Nelson, Mike Stabile"

import json
import os
import sys
import unittest
PROJECT_DIR = os.path.abspath(os.curdir)
sys.path.append(PROJECT_DIR)

from badges.rdfframework import *

class TestIri(unittest.TestCase):

    def test_iri(self):
        self.assertEqual(iri("https://schema.org/Person"), 
                         "<https://schema.org/Person>")
        self.assertEqual(iri("<obi:recipient>"),
                         "<obi:recipient>")

    def test_iri_errors(self):
        self.assertRaises(TypeError, iri, None)
        self.assertEqual(iri(""),
                         "<>")

class Test_is_not_null(unittest.TestCase):

    def test_is_not_null(self):
        self.assertFalse(is_not_null(None))
        self.assertFalse(is_not_null(""))

    def test_is_not_null_true(self):
        self.assertTrue(is_not_null("Test"))
        self.assertTrue(is_not_null(1234))

class Test_salt_processor(unittest.TestCase):

    def setUp(self):
        pass

    def test_mode_load(self):
        loaded_object = {"dataValue": 3456}
        self.assertEqual(
            salt_processor(loaded_object, "load"),
            3456)


    def test_salt_property(self):
        form = {"processedData": {},
                "prop": {"calcValue": None}}
        result = salt_processor(form, None, salt_property="sha1")
        self.assertIn(
            "sha1",
            result["processedData"])
        self.assertTrue(result['prop']['calcValue'])


    def test_salt_already_exists(self):
        form = {"processedData": {"https://schema.org/salt": 1234},
                "prop": {"calcValue": None},
                "propUri": "https://schema.org/salt"}
        self.assertEqual(
            salt_processor(form, None),
            form)


    def test_find_password_property(self):
        form = {"processedData": {},
                "propUri": "https://schema.org/salt",
                "prop": {"calcValue": None, "className": "OrganizationForm"}}
        result = salt_processor(form, None)
        self.assertIsNotNone(result)
            



class Test_run_processor(unittest.TestCase):

    def test_default(self):
        self.assertIsNone(run_processor(
            "kdr:UnknownProcessor",
            None,
            None))



class TestRdfClass(unittest.TestCase):

    def setUp(self):
        pass
        

    def test_init(self):
        pass

    def test_newUri(self):
        #self.assertEqual(self.person.newUri(), None)
        pass

    def test_save_none(self):
        #self.assertRaises(ValueError, self.person.save, data=None)
        pass

    def test_save_validate(self):
        #self.assertEquals(self.person.save({"giveName": "Mark", "email": "mtwain@email.com"}), True)
        pass

    def test_validatePrimaryKey(self):
        #self.assertEqual(self.person.validatePrimaryKey("help@gmail.com"), None)
               # "?uri a 0 .?uri <https://schema.org/email> 0 .")
        #self.assertEqual(self.person.validatePrimaryKey(None), None)
        pass

    def test__validateDependantProperties(self):
        pass

    def test_validateRequiredProperties(self):
        pass 
        

        
class TestRdfDatatype(unittest.TestCase):

    def setUp(self):
        self.langstring_instance = RdfDataType("langstring")
        self.literal_instance = RdfDataType("literal")
        self.obj_instance = RdfDataType("object")
        self.str_instance = RdfDataType("http://www.w3.org/2001/XMLSchema#string")

    def test_init(self):
        instance = RdfDataType("https://schema.org/Person")
        self.assertEqual(instance.name, "string")
        self.assertEqual(
            instance.iri, 
            "<http://www.w3.org/2001/XMLSchema#string>")
        #! Is this what we want as a prefix?
        self.assertEqual(instance.prefix, "xsd:string")

    def test_init_errors(self):
        self.assertRaises(TypeError, RdfDataType)

    def test_literal_datatype(self):
        self.assertEqual(self.literal_instance.name, "literal")
        self.assertEqual(self.literal_instance.prefix, "rdf:literal")
        self.assertEqual(
            self.literal_instance.iri,
            "<http://www.w3.org/1999/02/22-rdf-syntax-ns#literal>")


    def test_langstring_datatype(self):
        self.assertEqual(self.langstring_instance.prefix, "rdf:langstring")
        self.assertEqual(
            self.langstring_instance.iri,
            "<http://www.w3.org/1999/02/22-rdf-syntax-ns#langstring>")


    def test_object_datatype(self):
        self.assertEqual(self.obj_instance.prefix, "objInject")
        self.assertEqual(self.obj_instance.uri, "objInject")
        self.assertEqual(self.obj_instance.iri, "<http://www.w3.org/2001/XMLSchema#object>")

        
    def test_str_datatype(self):
        self.assertEqual(self.str_instance.prefix, "xsd:string")
        self.assertEqual(
            self.str_instance.iri,
            "<http://www.w3.org/2001/XMLSchema#string>")

    def test_sparql_object(self):
        self.assertEqual(
            self.obj_instance.sparql("http://knowledgelinks.io/example/1"),
            "<http://knowledgelinks.io/example/1>")
        #! Should raise an Error?
        self.assertEqual(
            self.obj_instance.sparql("Test String"),
            "<Test String>")

    def test_sparql_langstring(self):
        self.assertEqual(
            self.langstring_instance.sparql("eng"),
            '"eng"^^rdf:langstring')


    def test_sparql_literal(self):
        self.assertEqual(
            self.str_instance.sparql("Test String"),
            '"Test String"^^xsd:string')

    def test_sparql_boolean(self):
        boolean_instance = RdfDataType("boolean")
        self.assertEqual(
            boolean_instance.sparql(True),
            '"true"^^xsd:boolean')

            
    def test_sparql(self):
        badge_class_instance = RdfDataType(str(DC.name))
        self.assertEqual(
            badge_class_instance.sparql("Test"),
            '"Test"^^xsd:string')


class TestRdfFramework(unittest.TestCase):

    def setUp(self):
        pass


    def test_init(self):
        rdf_framework = RdfFramework()
        self.assertFalse(rdf_framework.app_initialzied)
        self.assertEqual(rdf_framework.rdf_class_dict, {}) 


    def test_loadApp(self):
        pass

    def test__generateClasses(self):
        pass

    def test__generateForms(self):
        pass
