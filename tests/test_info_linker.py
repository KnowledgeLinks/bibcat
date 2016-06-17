import os
import sys
import unittest

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
