__author__ = "Jeremy Nelson, Mike Stabile"

import logging
import os
import sys
import unittest
sys.path.append(os.path.abspath(os.path.curdir))
import ingesters
from ingesters.ingester import NS_MGR
from ingesters.csv import RowIngester

ingesters.MLOG_LVL = logging.CRITICAL
logging.getLogger("requests").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)


class TestRowIngester(unittest.TestCase):

    def setUp(self):
        self.ingester = RowIngester()

    def test_init(self):
        self.assertIsInstance(self.ingester, RowIngester)

    def test_defaults(self):
        self.assertEqual(
            self.ingester.base_url,
            "http://bibcat.org/")
        self.assertEqual(
            len(self.ingester.graph),
            0)
        self.assertTrue(
            len(self.ingester.rules_graph) < 1)
        self.assertIsNone(self.ingester.source)
        self.assertEqual(
            self.ingester.triplestore_url,
            "http://localhost:8080/blazegraph/sparql")


if __name__ == "__main__":
   unittest.main() 
