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


class TestRdfClass(unittest.TestCase):

    def setUp(self):
        self.person_json = json.loads("""{
    "Person": {
        "className": "Person",
        "classUri": "https://schema.org/Person",
        "primaryKey": "https://schema.org/email",
        "storageType": "object",
        "properties": {
            "email": {
                "propUri": "https://schema.org/email",
                "range": "http://www.w3.org/2001/XMLSchema#string",
                "storageType": "literal",
        "required": true
            },
            "familyName": {
                "propUri": "https://schema.org/familyName",
                "range": "http://www.w3.org/2000/01/rdf-schema#literal",
                "storageType": "literal",
        "required": true
            },
            "givenName": {
                "propUri": "https://schema.org/givenName",
                "range": "http://www.w3.org/2001/XMLSchema#string",
                "storageType": "literal",
        "required": true
            },
     "image": {
                "propUri": "https://schema.org/image",
                "range": ["http://schema.org/ImageObject","http://schema.org/URL"],
                "storageType": ["object","literal"],
        "required": false
            }
        }
    }
}""")
        self.person = RDFClass(self.person_json["Person"], "Person")
        

    def test_init(self):
        person = RDFClass(self.person_json["Person"], "Person")
        self.assertEqual(
            person.classUri, 
            "https://schema.org/Person")
        self.assertEqual(
            person.className,
            "Person")


    def test_newUri(self):
        self.assertEqual(self.person.newUri(), None)

    def test_save_none(self):
        self.assertRaises(ValueError, self.person.save, data=None)

    def test_save_validate(self):
        #self.assertEquals(self.person.save({"giveName": "Mark", "email": "mtwain@email.com"}), True)
        pass

    def test_validatePrimaryKey(self):
        self.assertEqual(self.person.validatePrimaryKey("help@gmail.com"), None)
               # "?uri a 0 .?uri <https://schema.org/email> 0 .")
        #self.assertEqual(self.person.validatePrimaryKey(None), None)

    def test__validateDependantProperties(self):
        pass

    def test_validateRequiredProperties(self):
        self.assertEqual(self.person.validateRequiredProperties(
            {"givenName": "Jane",
             "familyName": "Austen",
             "email": "ja@example.com"}),
            ["valid"])
        

        
class TestRdfDatatype(unittest.TestCase):

    def setUp(self):
        self.langstring_instance = RDFDataType("langstring")
        self.literal_instance = RDFDataType("literal")
        self.obj_instance = RDFDataType("object")
        self.str_instance = RDFDataType("http://www.w3.org/2001/XMLSchema#string")

    def test_init(self):
        instance = RDFDataType("https://schema.org/Person")
        self.assertEqual(instance.name, "https://schema.org/Person")
        self.assertEqual(
            instance.iri, 
            "<http://www.w3.org/2001/XMLSchema#https://schema.org/Person>")
        #! Is this what we want as a prefix?
        self.assertEqual(instance.prefix, "xsd:https://schema.org/Person")

    def test_init_errors(self):
        self.assertRaises(TypeError, RDFDataType)

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
        boolean_instance = RDFDataType("boolean")
        self.assertEqual(
            boolean_instance.sparql(True),
            '"true"^^xsd:boolean')

            
    def test_sparql(self):
        badge_class_instance = RDFDataType(str(DC.name))
        self.assertEqual(
            badge_class_instance.sparql("Test"),
            '"Test"^^xsd:http://purl.org/dc/elements/1.1/name')


class TestRDFFramework(unittest.TestCase):

    def setUp(self):
        pass


    def test_init(self):
        rdf_framework = RDFFramework()
        self.assertFalse(rdf_framework.app_initialzied)


    def test_loadApp(self):
        pass

    def test__generateClasses(self):
        pass

    def test__generateForms(self):
        pass
