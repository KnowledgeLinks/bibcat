import datetime


import logging
import os
import pymarc
import rdflib
import sys
import unittest
import uuid

sys.path.append(os.path.abspath(os.path.curdir))
import ingesters
import ingesters.marc as marc

marc.MLOG_LVL = logging.CRITICAL
logging.getLogger("requests").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

class TestMARC__handle_linked_pattern__(unittest.TestCase):

    def setUp(self):
        self.ingester = marc.MARCIngester(record=pymarc.Record())

    def test_exists(self):
        self.assertTrue(hasattr(self.ingester, "__handle_linked_pattern__"))

    def test_no_keywords(self):
        self.assertIsNone(
            self.ingester.__handle_linked_pattern__())

    def tearDown(self):
        self.ingester.graph.close()


class TestDeduplicatingInstances(unittest.TestCase):

    def setUp(self):
        self.ingester = marc.MARCIngester(record=pymarc.Record())


    def test_default_deduplicate_instances(self):
        self.ingester.deduplicate_instances()


class TestDeduplicatingAgents(unittest.TestCase):

    def setUp(self):
        self.ingester = marc.MARCIngester(record=pymarc.Record())

    def test_default_deduplicate_agents(self):
        self.ingester.deduplicate_agents(
            ingesters.ingester.NS_MGR.schema.oclc, 
            ingesters.ingester.NS_MGR.bf.Agent)


class TestMatchMARC(unittest.TestCase):

    def setUp(self):
        self.marc_record = pymarc.Record()
        self.marc_record.add_field(
            pymarc.Field('245', 
                ['1', '0'],
                ['a', 'This is a test:',
                 'b', 'and subtitle']))
        self.ingester = marc.MARCIngester(record=self.marc_record)


    def test_match_245_mainTitle(self):
        self.assertEqual(
            self.ingester.match_marc('M24510a'),
            ["This is a test:",])

    def test_match_245_subtitle(self):
        self.assertEqual(
            self.ingester.match_marc('M24510b'),
            ["and subtitle"])

class TestMARCUpdateLinkedClasses(unittest.TestCase):

    def setUp(self):
        self.entity = rdflib.URIRef("http://test.org/entity/1")
        self.ingester = marc.MARCIngester(record=pymarc.Record())

    def test_default_method(self):
        self.ingester.update_linked_classes(
            ingesters.ingester.NS_MGR.bf.Item,
            self.entity)

    def tearDown(self):
        pass

class TestMARCUpdateDirectProperties(unittest.TestCase):

    def setUp(self):
        self.entity = rdflib.URIRef("http://test.org/entity/1")
        self.ingester = marc.MARCIngester(record=pymarc.Record())


    def test_default_method(self):
        self.ingester.update_direct_properties(
            ingesters.ingester.NS_MGR.bf.Instance,
            self.entity)

class TestMARCUpdateOrderedLinkedClasses(unittest.TestCase):

    def setUp(self):
        self.entity = rdflib.URIRef("http://test.org/entity/1")
        self.ingester = marc.MARCIngester(record=pymarc.Record())
       
    def test_default_method(self):
        self.ingester.update_ordered_linked_classes(
            ingesters.ingester.NS_MGR.bf.Item,
            self.entity)



if __name__ == '__main__':
    unittest.main()
    

