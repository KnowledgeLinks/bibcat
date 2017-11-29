"""Unit tests for Geonames.org Linker"""
__author__ = "Jeremy Nelson"

import logging
import unittest

logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("rdflib").setLevel(logging.CRITICAL)

import bibcat.linkers.geonames as geonames

class TestDefaultGuessIRI(unittest.TestCase):

    def setUp(self):
        pass

    def test_no_values(self):
        self.assertRaises(TypeError, geonames.link_iri)

    def test_no_username(self):
        self.assertRaises(TypeError, geonames.link_iri, "Colorado Springs")

    def test_invalid_username(self):
        result = geonames.link_iri("Colorado Springs", "notGoodAtAllBIBCATUser")
        self.assertIsNone(result)


    def tearDown(self):
        pass

if __name__ == "__main__":
    unittest.main()
