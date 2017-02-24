__author__ = "Jeremy Nelson, Mike Stabile"

import logging
import os
import sys
import unittest
sys.path.append(os.path.abspath(os.path.curdir))
BIBCAT_BASE = os.path.abspath(
    os.path.split(
        os.path.dirname(__file__))[0])
PROJECT_BASE = os.path.split(BIBCAT_BASE)[0]
sys.path.append(PROJECT_BASE)
try:
    from instance import config
except ModuleNotFoundError:
    class Config(object):
        def __init__(self):
            self.BASE_URL = "http://bibcat.org/"
            self.TRIPLESTORE_URL = "http://localhost:9999/blazegraph/sparql"
             
    config = Config()

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
        if hasattr(config, 'BASE_URL'):
            self.assertEqual(
                self.ingester.base_url,
                config.BASE_URL)
        self.assertEqual(
            len(self.ingester.graph),
            0)
        self.assertTrue(
            len(self.ingester.rules_graph) < 1)
        self.assertIsNone(self.ingester.source)
        self.assertIn(
            self.ingester.triplestore_url,
            ['http://localhost:9999/blazegraph/sparql',
             config.TRIPLESTORE_URL])


if __name__ == "__main__":
   unittest.main() 
