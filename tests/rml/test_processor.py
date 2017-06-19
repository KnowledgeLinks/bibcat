__author__ = "Jeremy Nelson"

import os
import rdflib
import sys
import unittest
from unittest import mock
from types import SimpleNamespace
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

class TestRDFMappingLanguageProcessorGenerateTerms(unittest.TestCase):

    def setUp(self):
        self.processor = Processor(
            rml_rules=os.path.join(FIXURES_PATH,
                                   "rml-basic.ttl"))
        self.rr = rdflib.Namespace("http://www.w3.org/ns/r2rml#")
        self.test_map = SimpleNamespace()
        self.test_map.reference = None


    def test_default(self):
        self.assertRaises(KeyError, self.processor.generate_term)

    def test_termType_bnode(self):
        self.test_map.termType = self.rr.BlankNode
        self.assertIsInstance(
            self.processor.generate_term(term_map=self.test_map), 
            rdflib.BNode)

    def test_default_datatype(self):
        self.test_map.template = "{test_default}"
        term = self.processor.generate_term(term_map=self.test_map, test_default=1)
        self.assertIsInstance(term, rdflib.URIRef)

    def test_xsd_date_datatype(self):
        self.test_map.datatype = rdflib.XSD.date
        self.test_map.template = "{test_literal}"
        term = self.processor.generate_term(term_map=self.test_map, test_literal="2017")
        self.assertEqual(term.datatype,
            rdflib.XSD.date)

    def test_xsd_datetime_datatype(self):
        self.test_map.datatype = rdflib.XSD.dateTime
        self.test_map.template = "{test_literal}"
        term = self.processor.generate_term(term_map=self.test_map, test_literal="2017-06-19")
        self.assertEqual(term.datatype,
            rdflib.XSD.dateTime)

    def test_xsd_string_datatype(self):
        self.test_map.datatype = rdflib.XSD.string
        self.test_map.template = "{test_literal}"
        term = self.processor.generate_term(term_map=self.test_map, test_literal="A fine string")
        self.assertEqual(term.datatype,
            rdflib.XSD.string)
       
       

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main() 
