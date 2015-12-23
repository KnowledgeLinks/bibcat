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
        self.person = rdf_class(self.person_json["Person"])
        

    def test_init(self):
        person = rdf_class(self.person_json["Person"])
        self.assertEqual(
            person.classUri, 
            "https://schema.org/Person")


    def test_newUri(self):
        self.assertEqual(self.person.newUri(), None)

    def test_save(self):
        self.assertEqual(self.person.save(data=None), None)

    def test_validatePrimaryKey(self):
        print(self.person.primaryKey, self.person.properties[self.person.findPropName(self.person.primaryKey)]['storageType'])
        self.assertEqual(self.person.validatePrimaryKey("help@gmail.com"),
                "?uri a 0 .?uri <https://schema.org/email> 0 .")
        self.assertEqual(self.person.validatePrimaryKey(None), None)
        

        
class TestRdfDatatype(unittest.TestCase):

    def setUp(self):
        self.langstring_instance = rdf_datatype("langstring")
        self.literal_instance = rdf_datatype("literal")
        self.obj_instance = rdf_datatype("object")
        self.str_instance = rdf_datatype("http://www.w3.org/2001/XMLSchema#string")

    def test_init(self):
        instance = rdf_datatype("https://schema.org/Person")
        self.assertEqual(instance.name, "https://schema.org/Person")
        self.assertEqual(
            instance.iri, 
            "<http://www.w3.org/2001/XMLSchema#https://schema.org/Person>")
        #! Is this what we want as a prefix?
        self.assertEqual(instance.prefix, "xsd:https://schema.org/Person")

    def test_init_errors(self):
        self.assertRaises(TypeError, rdf_datatype)

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
        boolean_instance = rdf_datatype("boolean")
        self.assertEqual(
            boolean_instance.sparql(True),
            '"true"^^xsd:boolean')

            
    def test_sparql(self):
        badge_class_instance = rdf_datatype(str(DC.name))
        self.assertEqual(
            badge_class_instance.sparql("Test"),
            '"Test"^^xsd:http://purl.org/dc/elements/1.1/name')


