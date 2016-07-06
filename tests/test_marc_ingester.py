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

class TestDeduplicatingInstances(unittest.TestCase):

    def setUp(self):
        self.ingester = marc.MARCIngester(pymarc.Record())


    def test_default_deduplicate_instances(self):
        self.ingester.deduplicate_instances()


class TestDeduplicatingAgents(unittest.TestCase):

    def setUp(self):
        self.ingester = marc.MARCIngester(pymarc.Record())

    def test_default_deduplicate_agents(self):
        self.ingester.deduplicate_agents(
            ingesters.SCHEMA.oclc, 
            ingesters.BF.Agent)


class TestMatchMARC(unittest.TestCase):

    def setUp(self):
        self.marc_record = pymarc.Record()
        self.marc_record.add_field(
            pymarc.Field('245', 
                ['1', '0'],
                ['a', 'This is a test:',
                 'b', 'and subtitle']))
        self.ingester = marc.MARCIngester(self.marc_record)


    def test_match_245_mainTitle(self):
        self.assertEqual(
            self.ingester.match_marc('M24510a'),
            ["This is a test:",])

    def test_match_245_subtitle(self):
        self.assertEqual(
            self.ingester.match_marc('M24510b'),
            ["and subtitle"])

if __name__ == '__main__':
    unittest.main()
    

