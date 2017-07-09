import rdflib
import unittest
from bibcat import replace_iri, slugify, wikify

__author__ = "Jeremy Nelson"

class Test_replace_iri(unittest.TestCase):
    
    def setUp(self):
        self.graph = rdflib.Graph()

    def test_bnode_old_iri_exception(self):
        pass


class Test_slugify(unittest.TestCase):

    def setUp(self):
        pass

    def test_simple_name(self):
        self.assertEqual("mexico-city",
            slugify("Mexico City"))


class Test_wikify(unittest.TestCase):

    def setUp(self):
        pass

    def test_simple_name(self):
        self.assertEqual("Tokyo_Japan",
            wikify("Tokyo, Japan"))

    def tearDown(self):
        pass


if __name__ == '__main__':
    unittest.main()
