__author__ = "Jeremy Nelson"

import os
import rdflib
import sys
import unittest
import urllib.parse

sys.path.append(os.path.abspath(os.path.curdir))
import info_linker


class TestLinker(unittest.TestCase):

    def setUp(self):
        self.linker = info_linker.Linker()

    def test_init(self):
        self.assertTrue(isinstance(self.linker, info_linker.Linker))

    def test_run(self):
        self.assertTrue(hasattr(self.linker, 'run'))


class TestDBPediaLinker(unittest.TestCase):

    def setUp(self):
        self.linker = info_linker.DBPediaLinker()


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
            [info_linker.DBO.Book,])
        self.assertEqual(
            moby_dick_results[0].get('value'),
            "http://dbpedia.org/resource/Moby-Dick")

    def test_search_label_film(self):
        moby_dick_results = self.linker.search_label(
            "Moby Dick", 
            [info_linker.DBO.Film,])
        self.assertIn(
            {"dbo:class": info_linker.DBO.Film,
             "type": "uri",
             "value": "http://dbpedia.org/resource/Moby_Dick_(1971_film)"},
            moby_dick_results)

    def test_search_label_musical_work(self):
        john_wesley_harding_results = self.linker.search_label(
            "John Wesley Harding",
            [info_linker.DBO.MusicalWork,])
        self.assertIn(
            {"dbo:class": info_linker.DBO.MusicalWork,
             "type": "uri",
             "value": "http://dbpedia.org/resource/John_Wesley_Harding_(album)"},
            john_wesley_harding_results)


    def test_default_init(self):
        self.assertTrue(self.linker, info_linker.DBPediaLinker)
        self.assertEqual(
            self.linker.SPARQL_ENDPOINT,
            "http://dbpedia.org/sparql")

class TestLibraryOfCongressLinker(unittest.TestCase):

    def setUp(self):
        self.linker = info_linker.LibraryOfCongressLinker()

    def test_default_init(self):
        self.assertTrue(self.linker, info_linker.LibraryOfCongressLinker)
        self.assertEqual(
            self.linker.ID_LOC_URL,
            "http://id.loc.gov/")




if __name__ == "__main__":
    unittest.main()
