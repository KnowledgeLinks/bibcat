__author__ = "Jeremy Nelson, Mike Stabile"

import json
import os
import sys
import unittest

from flask import Flask

app = Flask(__name__)

app.config = {"ORGANIZATION": { "url": "http://knowledgelinks.io"},
              "TESTING": True,
              "DEBUG": True,
              "BASE_URL": "http://192.168.99.100:8081",
              "TRIPLESTORE_URL": "http://192.168.99.100:8081/bigdata/sparql",
              "REST_URL":  "http://192.168.99.100:8081/fedora/rest"} 

PROJECT_DIR = os.path.abspath(os.curdir)
sys.path.append(PROJECT_DIR)

from badges.rdfframework import *
import badges.rdfframework as framework
from badges.blueprint import open_badge

app.register_blueprint(open_badge)

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

class Test_csv_to_multi_prop_processor(unittest.TestCase):

    def setUp(self):
        self.tags = {
            "comment": "Tags for the badges.",
            "propertyProcessing": "http://knowledgelinks.io/ns/data-resources/CSVstringToMultiPropertyProcessor",
            "range": [
            {
              "storageType": "literal",
              "rangeClass": "http://www.w3.org/2001/XMLSchema#string"
            }
            ],
           "propUri": "https://w3id.org/openbadges#tags",
           "type": "http://www.w3.org/1999/02/22-rdf-syntax-ns#Property"}
      

    def test_load_mode(self):
        self.tags["dataValue"] = ["red", "green", "blue", "yellow"]
        result = csv_to_multi_prop_processor(self.tags, "load")
        self.assertEqual(result,
            "red, green, blue, yellow")


    def test_save_mode(self):
        self.tags["prop"] = {"new": "red, green, blue, yellow"}
        self.tags["processedData"] = {}
        result = csv_to_multi_prop_processor(self.tags)
        self.assertTrue(result['prop']['calcValue'])
        self.assertListEqual(
            sorted(result['processedData'][self.tags.get('propUri')]),
            sorted(["red", "green", "blue", "yellow"]))
        result2 = csv_to_multi_prop_processor(self.tags, "save")
        self.assertEqual(result, result2)


    def test_unknown_mode(self):
        #! Should an unknown mode raise an error instead of returning the
        #! object?
        self.assertEqual(
            self.tags,
            csv_to_multi_prop_processor(self.tags, "unknown"))



class Test_email_verification_processor(unittest.TestCase):

    def setUp(self):
        self.email = {
        "propertyProcessing": "http://knowledgelinks.io/ns/data-resources/EmailVerificationProcessor",
        "propUri": "https://schema.org/email",
        "comment": "email address.",
        "requiredByDomain": "https://schema.org/Person",
        "range": [
          {
            "storageType": "literal",
            "rangeClass": "http://www.w3.org/2001/XMLSchema#string"
          }
        ],
        "type": "http://www.w3.org/1999/02/22-rdf-syntax-ns#Property"
      }

    def test_load_mode(self):
        self.email["dataValue"] = "testuser@kl.io"
        result = email_verification_processor(self.email, "load")
        self.assertEqual(result, "testuser@kl.io")

    def test_save_mode(self):
        self.assertEqual(
            self.email,
            email_verification_processor(self.email, "save"))

    def test_unknown_mode(self):
        self.assertEqual(
            self.email,
            email_verification_processor(self.email, "unknown"))

class Test_password_processor(unittest.TestCase):

    def setUp(self):
        self.has_password = {
        "subPropertyOf": "http://knowledgelinks.io/ns/data-structures/securityProperty",
        "storageType": "object",
        "propUri": "http://knowledgelinks.io/ns/data-structures/hasPassword",
        "comment": "User's account password object",
        "requiredByDomain": "http://knowledgelinks.io/ns/data-structures/UserClass",
        "label": "User's password",
        "range": [
          {
            "storageType": "object",
            "rangeClass": "http://knowledgelinks.io/ns/data-structures/PasswordClass"
          }
        ],
        "type": "http://www.w3.org/1999/02/22-rdf-syntax-ns#Property"
      }


    def test_load_mode(self):
        fake_password = str(os.urandom(15))
        self.has_password["dataValue"] = fake_password
        self.assertEqual(
            password_processor(self.has_password, "load"),
            fake_password)

    def test_unknown_mode(self):
        self.assertEqual(
            self.has_password,
            password_processor(self.has_password, "unknown"))
 

    def test_verify_mode(self):
        pass
        
class Test_salt_processor(unittest.TestCase):

    def setUp(self):
        pass

    def test_load_mode(self):
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
                "prop": {"calcValue": None, "className": "Organization"}}
        self.assertRaises(AttributeError, salt_processor, obj=form, mode=None)



class Test_run_processor(unittest.TestCase):

    def test_default(self):
        self.assertIsNone(run_processor(
            "kdr:UnknownProcessor",
            None,
            None))



class TestRdfClass(unittest.TestCase):

    def setUp(self):
        self.person_json = {
    "properties": {
      "email": {
        "propertyProcessing": "http://knowledgelinks.io/ns/data-resources/EmailVerificationProcessor",
        "propUri": "https://schema.org/email",
        "comment": "email address.",
        "requiredByDomain": "https://schema.org/Person",
        "range": [
          {
            "storageType": "literal",
            "rangeClass": "http://www.w3.org/2001/XMLSchema#string"
          }
        ],
        "type": "http://www.w3.org/1999/02/22-rdf-syntax-ns#Property"
      },
      "affliation": {
        "label": "Affiliated with",
        "range": [
          {
            "storageType": "object",
            "rangeClass": "https://schema.org/Organization"
          }
        ],
        "propUri": "https://schema.org/affliation",
        "type": "http://www.w3.org/1999/02/22-rdf-syntax-ns#Property"
      },
      "familyName": {
        "requiredByDomain": "https://schema.org/Person",
        "comment": "Last name or family name for an individual.",
        "range": [
          {
            "storageType": "literal",
            "rangeClass": "http://www.w3.org/2001/XMLSchema#string"
          }
        ],
        "propUri": "https://schema.org/familyName",
        "type": "http://www.w3.org/1999/02/22-rdf-syntax-ns#Property"
      },
      "givenName": {
        "requiredByDomain": "https://schema.org/Person",
        "comment": "First name or given name for an individual.",
        "range": [
          {
            "storageType": "literal",
            "rangeClass": "http://www.w3.org/2001/XMLSchema#string"
          }
        ],
        "propUri": "https://schema.org/givenName",
        "type": "http://www.w3.org/1999/02/22-rdf-syntax-ns#Property"
      }
    },
    "storageType": "object",
    "primaryKey": "https://schema.org/email",
    "classUri": "https://schema.org/Person"
    }
        self.person = framework.RdfClass(self.person_json, "Person")
        

    def test_init(self):
        self.assertIsNotNone(framework.RdfClass({}, None))

    def test_get_property_name(self):
        for name, val in self.person_json["properties"].items():
            self.assertEqual(
                self.person.get_property(prop_name=name),
                val)

    def test_get_property_uri(self):
        self.assertEqual(
            self.person.get_property(prop_uri='https://schema.org/givenName'),
            self.person_json["properties"]["givenName"])


    def test_list_properties(self):
        self.assertEqual(
            self.person.list_properties(),
            set(['https://schema.org/familyName', 
             'https://schema.org/email', 
             'https://schema.org/givenName', 
             'https://schema.org/affliation'])
            )

    def test_list_required(self):
        self.assertEqual(
            self.person.list_required(),
            set(['https://schema.org/familyName', 
             'https://schema.org/email', 
             'https://schema.org/givenName']))

    def test_new_uri(self):
        self.assertEqual(self.person.new_uri(), None)

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
        self.assertEqual(instance.prefix, "xsd:string")

    def test_init_errors(self):
        self.assertRaises(AttributeError, RdfDataType)

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
        self.assertEqual(
            self.obj_instance.iri, 
            "<http://www.w3.org/2001/XMLSchema#object>")

        
    def test_str_datatype(self):
        self.assertEqual(self.str_instance.prefix, "xsd:string")
        self.assertEqual(
            self.str_instance.iri,
            "<http://www.w3.org/2001/XMLSchema#string>")

    def test_sparql_object(self):
        self.assertEqual(
            self.obj_instance.sparql("http://knowledgelinks.io/example/1"),
            "<http://knowledgelinks.io/example/1>")
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
        framework.current_app = app
        self.rdf_framework = framework.RdfFramework()
        self.user_name = {
            "type": "http://www.w3.org/1999/02/22-rdf-syntax-ns#Property",
	    "propUri": "http://knowledgelinks.io/ns/data-structures/userName",
	    "range": [
                {
                   "storageType": "literal",
                   "rangeClass": "http://www.w3.org/2001/XMLSchema#string"
                }
           ],
           "subPropertyOf": "http://knowledgelinks.io/ns/data-structures/securityProperty",
	   "comment": "Individual's username",
           "label": "Username",
	   "requiredByDomain": "http://knowledgelinks.io/ns/data-structures/UserClass"
        }


    def test_defaults(self):
        self.assertFalse(framework.RdfFramework.app_initialized)
        self.assertEqual(framework.RdfFramework.rdf_class_dict, {})


    def test_init(self):
        framework.current_app = app
        rdf_framework = framework.RdfFramework()
        self.assertTrue(rdf_framework.app_initialized)
        
    def test_get_class_name(self):
        self.assertEqual(
            self.rdf_framework.get_class_name(
                "https://schema.org/Person"),
	    "Person")


    def test_get_class_name_none(self):
        self.assertEqual(
            self.rdf_framework.get_class_name(
                "https://schema.org/Thing"),
            "")

    def test_get_property_class_name_prop_name(self):
        self.assertEqual(
            self.rdf_framework.get_property(
                class_name="UserClass",
                prop_name="userName"),
            [self.user_name,])

    def test_get_property_class_name_prop_uri(self):
        self.assertEqual(
            self.rdf_framework.get_property(
                class_name="UserClass",
		prop_uri="http://knowledgelinks.io/ns/data-structures/userName"),
            [self.user_name,])


    def test_get_property_class_uri_prop_name(self):
        expires = {
            "defaultVal": "now + 360",
            "type": "http://www.w3.org/1999/02/22-rdf-syntax-ns#Property",
	    "propUri": "https://w3id.org/openbadges#expires",
            "range": [
                {
                    "storageType": "literal",
                    "rangeClass": "http://www.w3.org/2000/01/rdf-schema#datetime"
                }
	    ],
	   "comment": "Timestamp when badge expires."
	}
        self.assertEqual(
            self.rdf_framework.get_property(
                class_uri="https://w3id.org/openbadges#Assertion",
		prop_name="expires"),
            [expires,])

    def test_loadApp(self):
        pass

    def test__generateClasses(self):
        pass

    def test__generateForms(self):
        pass
