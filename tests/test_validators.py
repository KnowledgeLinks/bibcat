__author__ = "Jeremy Nelson, Mike Stabile"

import os
import sys
import unittest

from ..rdfframework.validators import *

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
