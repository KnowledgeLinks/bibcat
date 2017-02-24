__author__ = "Jeremy Nelson"

import os
import rdflib
import sys
import unittest
import urllib.parse

sys.path.append(os.path.abspath(os.path.curdir))
from linkers import NS_MGR
import linkers.dbpedia as dbpedia


class TestDBPediaLinker(unittest.TestCase):

    def setUp(self):
        self.linker = dbpedia.DBPediaLinker()


    def test_enhance_uri_default(self):
        test_uri = rdflib.URIRef("http://bibcat.org/sample-uri")
        enhanced_graph = self.linker.enhance_uri(
            test_uri, 
            "http://dbpedia.org/resource/Moby-Dick")
        self.assertTrue(isinstance(enhanced_graph, rdflib.Graph))

    def test_search_label_default(self):
        moby_dick_results = self.linker.search_label("Moby Dick")
        self.assertEqual(
            len(moby_dick_results),
            7)
    def test_search_label_book(self):
        moby_dick_results = self.linker.search_label(
            "Moby Dick", 
            [NS_MGR.dbo.Book,])
        self.assertEqual(
            moby_dick_results[0].get('value'),
            "http://dbpedia.org/resource/Moby-Dick")

    def test_search_label_film(self):
        moby_dick_results = self.linker.search_label(
            "Moby Dick", 
            [NS_MGR.dbo.Film,])
        self.assertIn(
            {"dbo:class": NS_MGR.dbo.Film,
             "type": "uri",
             "value": "http://dbpedia.org/resource/Moby_Dick_(1978_film)"},
            moby_dick_results)

    def test_search_label_musical_work(self):
        john_wesley_harding_results = self.linker.search_label(
            "John Wesley Harding",
            [NS_MGR.dbo.MusicalWork,])
        self.assertIn(
            {"dbo:class": NS_MGR.dbo.MusicalWork,
             "type": "uri",
             "value": "http://dbpedia.org/resource/John_Wesley_Harding_(album)"},
            john_wesley_harding_results)


    def test_default_init(self):
        self.assertIsInstance(self.linker, dbpedia.DBPediaLinker)
        self.assertEqual(
            self.linker.SPARQL_ENDPOINT,
            "http://dbpedia.org/sparql")

if __name__ == "__main__":
    unittest.main()
