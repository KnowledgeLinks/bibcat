"Tests custom Marmot JSON Ingester"
__author__ = "Jeremy Nelson"

import os
import sys
import unittest
from unittest import mock

from bibcat.ingesters.marmot import MarmotIngester

class TestMarmotIngester(unittest.TestCase):

    def setUp(self):
        pass

    def test_init_fails(self):
        # Testing default args for MarmotIngester
        self.assertRaises(ValueError, MarmotIngester)
        
    def test_init_success(self):
        ingester = MarmotIngester(rules_ttl='bibcat-base.ttl')


if __name__ == '__main__':
    unittest.main()
