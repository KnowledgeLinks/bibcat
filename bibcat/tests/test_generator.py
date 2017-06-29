import unittest
import os
import sys
import unittest
sys.path.append(os.path.abspath(os.path.curdir))
from generators.generator import Generator, config

class TestGenerator(unittest.TestCase):

    def setUp(self):
        del(config.BASE_URL)
        self.generator = Generator()

    def test_defaults(self):
        self.assertEqual(
            self.generator.triplestore_url,
            "http://localhost:9999/blazegraph/sparql")
        self.assertEqual(
            self.generator.base_url,
            "http://bibcat.org/")

if __name__ == '__main__':
    unittest.main()
