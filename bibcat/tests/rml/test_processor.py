__author__ = "Jeremy Nelson"

import os
import rdflib
import sys
import unittest
from unittest import mock
from types import SimpleNamespace
try:
    import bibcat.rml.processor as processor
    import bibcat    
except ImportError:
    sys.path.append(os.path.abspath("."))
    import bibcat.rml.processor as processor
    import bibcat

TESTS_PATH = os.path.dirname(os.path.abspath(__file__))
FIXURES_PATH = os.path.join(
    TESTS_PATH, 
    "fixures")

class TestRDFMappingLanguageProcessor(unittest.TestCase):

    def setUp(self):
        pass

    def test_defaults(self):
        self.assertRaises(TypeError, processor.Processor)
     
    def test_bibcat_base(self):
        base_processor = processor.Processor(
            rml_rules=os.path.join(FIXURES_PATH,
                                   "rml-basic.ttl"))
        self.assertTrue(isinstance(base_processor.rml, rdflib.Graph))

    def test_bibcat_rules_missing_rml_rules_error(self):
        self.assertRaises(TypeError, processor.Processor, rml_rules=None)
        # Windows error
        if sys.platform.startswith("win"):
            self.assertRaises(PermissionError, processor.Processor, rml_rules="")
        else:
            self.assertRaises(IsADirectoryError, processor.Processor, rml_rules="")
        self.assertRaises(Exception, processor.Processor, rml_rules=[])


    def test_bibcat_rules_blank_graphs_rml_rules_error(self):
        self.assertRaises(Exception, processor.Processor, rml_rules=rdflib.Graph())
        self.assertRaises(Exception, 
            processor.Processor, 
            rml_rules=rdflib.ConjunctiveGraph())
        

    def test_bibcat_acceptable_path_rules(self):
        raw_rml = os.path.join(FIXURES_PATH,
                               "rml-basic.ttl")
        self.assertTrue(os.path.exists(raw_rml))
        self.assertTrue(
            isinstance(processor.Processor(raw_rml),
                       processor.Processor))
                      
    def test_bibcat_package_rule(self):
        self.assertTrue(
            isinstance(processor.Processor("bibcat-base.ttl"),
                      processor.Processor))
 
    def test_bibcat_acceptable_list_rules(self):
        rules = []
        for name in ["rml-basic.ttl", "rml-basic.ttl"]:
             rules.append(os.path.join(FIXURES_PATH, name))
        self.assertTrue(
            isinstance(processor.Processor(rules),
                       processor.Processor))
    
    def test_version(self):
        # Should be same as bibcat
        self.assertEqual(processor.__version__,
                         bibcat.__version__)

        

    def tearDown(self):
        pass 

class TestRDFMappingLanguageProcessorGenerateTerms(unittest.TestCase):

    def setUp(self):
        self.processor = processor.Processor(
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
        term = self.processor.generate_term(
            term_map=self.test_map, 
            test_literal="A fine string")
        self.assertEqual(term.datatype,
            rdflib.XSD.string)

    def test_template_default_literal(self):
        literal_value = "Default Literal String"
        self.test_map.template = "{test_literal}"
        term = self.processor.generate_term(
            term_map=self.test_map,
            test_literal=literal_value)
        self.assertEqual(str(term),
            literal_value)

    def test_template_default_url(self):
        self.test_map.template = "http://test.io/{id}"
        uri_term = self.processor.generate_term(
            term_map=self.test_map,
            id="1234")
        self.assertEqual(str(uri_term),
            "http://test.io/1234")

      
    def test_template_errors(self):
        self.test_map.template = "{test_literal}"
        self.assertRaises(KeyError, 
            self.processor.generate_term,
            term_map=self.test_map,
            test_not_literal="1234")

    def tearDown(self):
        pass


class TestGetObjectInternalFunction(unittest.TestCase):

    def setUp(self):
        pass

    def test_default_error(self):
        # Binding Required
        self.assertRaises(TypeError, processor.__get_object__) 

    def test_None(self):
        self.assertEqual(processor.__get_object__(None), None)

    def test_simple_binding(self):
        binding = {"value": "1234"}
        self.assertEqual(processor.__get_object__(binding),
            rdflib.Literal(binding.get('value')))

    def tearDown(self):
        pass

class Test__graph__Method(unittest.TestCase):

    def setUp(self):
        self.processor = processor.Processor(
            rml_rules=os.path.join(FIXURES_PATH,
                                   "rml-basic.ttl"))

    def test_default(self):
        self.assertIsInstance(self.processor.__graph__(),
                              rdflib.Graph)

    def test_namespaces(self):
        new_graph = self.processor.__graph__()
        self.assertListEqual(
            [n for n in sorted(new_graph.namespace_manager.namespaces())], 
            [n for n in sorted(self.processor.rml.namespace_manager.namespaces())])

    def tearDown(self):
        pass

class Test__handle_parents__Method(unittest.TestCase):

    def setUp(self):
        self.processor = processor.Processor(
            rml_rules=os.path.join(FIXURES_PATH,
                                   "rml-basic.ttl"))

    def test_errors(self):
        self.assertRaises(KeyError, self.processor.__handle_parents__)
        self.assertRaises(KeyError, 
            self.processor.__handle_parents__,
            parent_map = SimpleNamespace())

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main() 
