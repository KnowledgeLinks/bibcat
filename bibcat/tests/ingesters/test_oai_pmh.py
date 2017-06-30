"""Tests oai_pmh module's OAI_PMH base class and Islandora subclass"""
__author__ = "Jeremy Nelson"

import os
import sys
import unittest
from unittest import mock
try:
    from bibcat.ingesters.oai_pmh import OAIPMHIngester, IslandoraIngester
except ImportError:
    BIBCAT_BASE = os.path.abspath(".")
    sys.path.append(BIBCAT_BASE)
    from bibcat.ingesters.oai_pmh import OAIPMHIngester, IslandoraIngester

# Mock of OAI-PMH Fee
def mocked_oai_pmh(*args, **kwargs):
    class MockOAIPMHResponse(object):

        def __init__(self, xml, status_code):
            self.xml = xml
            self.status_code = status_code

        @property
        def text(self):
            return self.xml  

        
    fixures_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 
        "fixures")
    if args[0] == 'http://bibcat.org/oai2?verb=ListMetadataFormats':
        with open(os.path.join(fixures_path, 
                               "list-metadata-formats.xml")) as fo:
            list_metadata_xml = fo.read()
        return MockOAIPMHResponse(list_metadata_xml, 200)
    elif args[0] == 'http://bibcat.org/oai2?verb=ListIdentifiers&metadataPrefix=oai_dc':
        with open(os.path.join(fixures_path, "first-dc-ids.xml")) as fo:
            first_dc_ids_xml = fo.read()
        return MockOAIPMHResponse(first_dc_ids_xml, 200)
    elif args[0] == 'http://bibcat.org/oai2?verb=ListIdentifiers&resumptionToken=2340121':
        with open(os.path.join(fixures_path, "final-dc-ids.xml")) as fo:
            final_dc_ids = fo.read()
        return MockOAIPMHResponse(final_dc_ids, 200)
    else:
        return MockOAIPMHResponse(None, 404)


class TestOAI_PMHIngester(unittest.TestCase):

    def setUp(self):
        """Creates test environment"""
        pass

    def test_defaults(self):
        self.assertRaises(ValueError, OAIPMHIngester)

    def test_class_constants(self):
        self.assertTrue(hasattr(OAIPMHIngester, "IDENT_XPATH"))
        self.assertTrue(hasattr(OAIPMHIngester, "TOKEN_XPATH")) 

    @mock.patch("bibcat.ingesters.oai_pmh.requests.get", 
        side_effect=mocked_oai_pmh)
    def test_init_repo(self, mock_get):
        oai_ingester = OAIPMHIngester(repository='http://bibcat.org/oai2')
        self.assertEqual(oai_ingester.oai_pmh_url,
                         'http://bibcat.org/oai2')
        self.assertEqual(oai_ingester.metadataPrefix, "oai_dc")


    def tearDown(self):
        pass

class TestIslandoraIngester(unittest.TestCase):

    def setUp(self):
        pass

    def test_defaults(self):
        self.assertRaises(KeyError, IslandoraIngester)

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()
