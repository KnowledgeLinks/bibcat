__author__ = "Jeremy Nelson"

import os
import rdflib
import sys
import unittest
from unittest import mock
sys.path.append(os.path.abspath("."))
from bibcat.rml.processor import Processor

TESTS_PATH = os.path.dirname(os.path.abspath(__file__))
FIXURES_PATH = os.path.join(
    TESTS_PATH, 
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

    def test_bibcat_rules_missing_rml_rules_error(self):
        self.assertRaises(TypeError, Processor, rml_rules=None)
        self.assertRaises(ValueError, Processor, rml_rules="")
        self.assertRaises(Exception, Processor, rml_rules=[])


    def test_bibcat_rules_blank_graphs_rml_rules_error(self):
        self.assertRaises(Exception, Processor, rml_rules=rdflib.Graph())
        self.assertRaises(Exception, 
            Processor, 
            rml_rules=rdflib.ConjunctiveGraph())
        

    def test_bibcat_acceptable_path_rules(self):
        raw_rml = os.path.join(FIXURES_PATH,
                               "rml-basic.ttl")
        self.assertTrue(os.path.exists(raw_rml))
        self.assertTrue(
            isinstance(Processor(raw_rml),
                       Processor))
                       
    def test_bibcat_acceptable_list_rules(self):
        rules = []
        for name in ["rml-basic.ttl", "rml-basic.ttl"]:
             rules.append(os.path.join(FIXURES_PATH, name))
        self.assertTrue(
            isinstance(Processor(rules),
                       Processor))


    def tearDown(self):
        pass 

if __name__ == '__main__':
    unittest.main() 
