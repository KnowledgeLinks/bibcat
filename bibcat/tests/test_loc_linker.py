__author__ = "Jeremy Nelson"

import os
import rdflib
import sys
import unittest
import urllib.parse

sys.path.append(os.path.abspath(os.path.curdir))
from linkers import NS_MGR
import linkers.loc as loc

class TestLibraryOfCongressLinker(unittest.TestCase):

    def setUp(self):
        self.linker = loc.LibraryOfCongressLinker()

    def test_default_init(self):
        self.assertTrue(self.linker, loc.LibraryOfCongressLinker)
        self.assertEqual(
            self.linker.ID_LOC_URL,
            "http://id.loc.gov/")

if __name__ == "__main__":
    unittest.main()

