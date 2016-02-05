__author__ = "Jeremy Nelson, Mike Stabile"

import unittest

from flask import Flask
from .badges.blueprint import open_badge

app = Flask(__name__)

app.config = {"ORGANIZATION": { "url": "http://knowledgelinks.io"},
              "TESTING": True,
              "DEBUG": True,
              "BASE_URL": "http://localhost:8080"}
app.config["TRIPLESTORE_URL"] = "{}/bigdata/sparql".format(
    app.config["BASE_URL"])
app.config["REST_URL"] = "{}/fedora/rest".format(
    app.config["BASE_URL"])

app.register_blueprint(open_badge)

class TestRdfFramework(unittest.TestCase):

    def setUp(self):
        framework.current_app = app
        self.rdf_framework = framework.RdfFramework()
        self.expires = {
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
        self.assertEqual(
            self.rdf_framework.get_property(
                class_uri="https://w3id.org/openbadges#Assertion",
		        prop_name="expires"),
            [self.expires,])

    def test_get_property_class_uri_prop_uri(self):
        self.assertEqual(
            self.rdf_framework.get_property(
                class_uri="https://w3id.org/openbadges#Assertion",
				prop_uri="https://w3id.org/openbadges#expires"),
            [self.expires,])

    def test_get_save_order(self):
        rdf_form = {}
        self.assertEqual(
            self.rdf_framework._get_save_order(
                rdf_form),
			{"saveOrder": [],
             "reverseDependancies":[]})

    def test_loadApp(self):
        pass

    def test__generateClasses(self):
        pass

    def test__generateForms(self):
        pass
