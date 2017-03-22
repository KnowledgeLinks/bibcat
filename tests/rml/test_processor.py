__author__ = "Jeremy Nelson"

import os
import rdflib
import sys
import unittest
from unittest import mock
sys.path.append(os.path.abspath("."))
from bibcat.rml.processor import Processor

FIXURES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    "fixures")

class TestRDFMappingLanguageProcessor(unittest.TestCase):

    def setUp(self):
        pass

    def test_defaults(self):
        self.assertRaises(TypeError, Processor)
     
    def test_bibcat_base(self):
        processor = Processor(
            rml_rules=os.path.join(FIXURES_PATH,
                                   "rml-basic.ttl"))
        self.assertTrue(isinstance(processor.rml, rdflib.Graph))

    def tearDown(self):
        pass 

if __name__ == '__main__':
    unittest.main() 
