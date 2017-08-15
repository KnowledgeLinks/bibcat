__author__ = "Jeremy Nelson"

import unittest

import bibcat.ingesters.rels_ext as rels_ext
from bibcat.ingesters.rels_ext import BF

class TestDefaultRELSEXTIngester(unittest.TestCase):

    def setUp(self):
        self.ingester = rels_ext.RELSEXTIngester()

    def test_default_init(self):
        ingester = rels_ext.RELSEXTIngester()

    def test_default_namespaces(self):
        self.assertEqual(self.ingester.xml_ns.get("fedora"),
            "info:fedora/fedora-system:def/relations-external#")


    def tearDown(self):
        pass
        

if __name__ == '__main__':
    unittest.main()
