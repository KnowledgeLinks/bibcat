__author__ = "Jeremy Nelson, Mike Stabile"

import unittest

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
