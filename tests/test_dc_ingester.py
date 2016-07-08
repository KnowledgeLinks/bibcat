import logging
import os
import rdflib
import requests
import sys
import unittest

import xml.etree.ElementTree as etree

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import ingesters
import ingesters.dc as dc

with open(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            "dpl-dc-example.xml")) as raw_file:
    dc_fixure = raw_file.read()

class TestInitDCIngester(unittest.TestCase):

    def setUp(self):
        self.ingester = dc.DCIngester()

    def test_default_is_ingester(self):
        self.assertIsInstance(self.ingester,
            dc.DCIngester)

    def test_dc_xml(self):
        ingester = dc.DCIngester(dc_fixure)
        self.assertIsInstance(ingester,
            dc.DCIngester)


class TestDC__handle_linked_pattern__(unittest.TestCase):

    def setUp(self):
        self.ingester = dc.DCIngester(dc_fixure)

    def test_exists(self):
        self.assertTrue(hasattr(self.ingester, "__handle_linked_pattern__"))

    def test_no_keywords(self):
        self.assertRaises(
            AssertionError,
            self.ingester.__handle_linked_pattern__)

    def tearDown(self):
        self.ingester.graph.close()


class TestDCUpdateLinkedClasses(unittest.TestCase):

    def setUp(self):
        self.entity = rdflib.URIRef("http://test.org/entity/1")
        self.ingester = dc.DCIngester(dc_fixure)

    def test_default_method(self):
        self.ingester.update_linked_classes(
            ingesters.BF.Item,
            self.entity)

    def tearDown(self):
        pass

class TestDCUpdateDirectProperties(unittest.TestCase):

    def setUp(self):
        self.entity = rdflib.URIRef("http://test.org/entity/1")
        self.ingester = dc.DCIngester()


    def test_default_method(self):
        self.ingester.update_direct_properties(
            ingesters.BF.Instance,
            self.entity)

class TestDCUpdateOrderedLinkedClasses(unittest.TestCase):

    def setUp(self):
        self.entity = rdflib.URIRef("http://test.org/entity/1")
        self.ingester = dc.DCIngester(dc_fixure)
       
    def test_default_method(self):
        self.ingester.update_ordered_linked_classes(
            ingesters.BF.Item,
            self.entity)


if __name__ == '__main__':
   unittest.main() 
