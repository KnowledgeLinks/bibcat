"Tests custom Marmot JSON Ingester"
__author__ = "Jeremy Nelson"

import os
import sys
import unittest
from unittest import mock

from bibcat.ingesters.marmot import MarmotIngester

class TestMarmotIngester(unittest.TestCase):

    def setUp(self):
        self.ingester = MarmotIngester(rules_ttl='bibcat-base.ttl')

    def test_init_fails(self):
        # Testing default args for MarmotIngester
        self.assertRaises(ValueError, MarmotIngester)
        
    def test_init_success(self):
        ingester = MarmotIngester(rules_ttl='bibcat-base.ttl')

    def test_load_members(self):
        # Tests internal load members function
        self.assertRaises(TypeError, self.ingester.__load_members__)

    def test_load_feed_url(self):
        self.assertRaises(TypeError, self.ingester.load_feed_url)

if __name__ == '__main__':
    unittest.main()
