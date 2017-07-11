__author__ = "Jeremy Nelson"


import unittest
import rdflib
from bibcat.rml.processor import XMLProcessor

class TestXMLProcessorInit(unittest.TestCase):

    def setUp(self):
        pass

    def test_default_execptions(self):
        self.assertRaises(Exception, XMLProcessor)
        

    def test_default_base(self):
        base_rules = rml_rules=["bibcat-base.ttl"]
        processor = XMLProcessor(rml_rules=base_rules)
        self.assertEqual(len(processor.rml), 16)

   

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main() 
