__author__ = "Jeremy Nelson"

import sys
import unittest

from bibcat.rml.processor import JSONProcessor

class TestJSONProcessorInit(unittest.TestCase):

    def setUp(self):
        pass

    def test_default_exceptions(self):
        self.assertRaises(Exception, JSONProcessor)
        # Windows error
        if sys.platform.startswith("win"):
            self.assertRaises(PermissionError, JSONProcessor, rml_rules="")
        else:
            self.assertRaises(IsADirectoryError, JSONProcessor, rml_rules="")
        self.assertRaises(Exception, JSONProcessor, rml_rules=[])

    def test_default_base(self):
        processor = JSONProcessor(rml_rules=["bibcat-base.ttl"])
        self.assertEqual(len(processor.rml), 16)

        

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()
