__author__ = "Jeremy Nelson"

import os
import rdflib
import sys
import unittest
import urllib.parse

sys.path.append(os.path.abspath(os.path.curdir))
import linkers


class TestLinker(unittest.TestCase):

    def setUp(self):
        self.linker = linkers.Linker()

    def test_init(self):
        self.assertIsInstance(self.linker, linkers.Linker)

    def test_run(self):
        self.assertTrue(hasattr(self.linker, 'run'))





if __name__ == "__main__":
    unittest.main()
