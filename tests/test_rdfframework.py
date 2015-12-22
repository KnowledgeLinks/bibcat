__author__ = "Jeremy Nelson, Mike Stabile"

import os
import sys
import unittest
PROJECT_DIR = os.path.abspath(os.curdir)
sys.path.append(PROJECT_DIR)

from badges.rdfframework import *

class TestIri(unittest.TestCase):

    def test_iri(self):
        self.assertEqual(iri("https://schema.org/Person"), 
                         "<https://schema.org/Person>")
        self.assertEqual(iri("<obi:recipient>"),
                         "<obi:recipient>")

    def test_iri_errors(self):
        self.assertRaises(TypeError, iri, None)
        self.assertEqual(iri(""),
                         "<>")


class TestRdfClass(unittest.TestCase):

    def setUp(self):
        pass

class TestRdfDatatype(unittest.TestCase):

    def setUp(self):
        pass

    def test_init(self):
        instance = rdf_datatype("https://schema.org/Person")
        self.assertEqual(instance.name, "https://schema.org/Person")
        self.assertEqual(instance.iri, "<https://schema.org/Person>")

