import logging
import os
import rdflib
import requests
import sys
import unittest

sys.path.append(os.path.abspath(os.path.curdir))
import ingesters
import ingesters.mods as mods

ingesters.MLOG_LVL = logging.CRITICAL
logging.getLogger("requests").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

class TestMODS__handle_linked_pattern__(unittest.TestCase):

    def setUp(self):
        self.ingester = mods.MODSIngester()

    def test_exists(self):
        self.assertTrue(hasattr(self.ingester, "__handle_linked_pattern__"))

    def test_no_keywords(self):
        self.assertRaises(
            AttributeError,
            self.ingester.__handle_linked_pattern__)

    def tearDown(self):
        self.ingester.graph.close()

class TestInitMODSIngester(unittest.TestCase):

    def setUp(self):
        self.ingester = mods.MODSIngester()

    def test_defaults(self):
        self.assertEqual(
            self.ingester.base_url,
            "http://bibcat.org/")
        self.assertEqual(
            len(self.ingester.graph),
            0)
        self.assertTrue(
            len(self.ingester.rules_graph) > 1)
        self.assertIsNone(self.ingester.source)
        self.assertEqual(
            self.ingester.triplestore_url,
            "http://localhost:8080/blazegraph/sparql")

class TestMODSUpdateDirectProperties(unittest.TestCase):

    def setUp(self):
        self.entity = rdflib.URIRef("http://test.org/entity/1")
        self.ingester = mods.MODSIngester()


    def test_default_method(self):
        self.ingester.update_direct_properties(
            ingesters.BF.Instance,
            self.entity)

class TestMODSUpdateLinkedClasses(unittest.TestCase):

    def setUp(self):
        self.entity = rdflib.URIRef("http://test.org/entity/1")
        self.ingester = mods.MODSIngester()

    def test_default_method(self):
        self.ingester.update_linked_classes(
            ingesters.BF.Item,
            self.entity)

class TestMODSUpdateOrderedLinkedClasses(unittest.TestCase):

    def setUp(self):
        self.entity = rdflib.URIRef("http://test.org/entity/1")
        self.ingester = mods.MODSIngester()
       
    def test_default_method(self):
        self.ingester.update_ordered_linked_classes(
            ingesters.BF.Item,
            self.entity)
       
if __name__ == '__main__':
    unittest.main()
