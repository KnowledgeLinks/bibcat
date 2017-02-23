import os
import requests
import rdflib
import sys
import unittest

from unittest.mock import MagicMock

sys.path.append(os.path.abspath(os.path.curdir))
from generators.generator  import new_graph
from generators.work import WorkGenerator

class MockResponse(object):

    def __init__(self):
        self.status_code = 200
        self.output = {"results": {"bindings": []}}

    def json(self):
        return self.output



class TestEmptyWorkGenerator(unittest.TestCase):

    def setUp(self):
        requests.post = MagicMock(return_value=MockResponse())
        self.work_generator = WorkGenerator()
        self.instance_uri = self.work_generator.__generate_uri__()

    def test_init(self):
        self.assertTrue(
            isinstance(self.work_generator, 
                       WorkGenerator))
        # Default Blazegraph triplestore runs on localhost through semantic
        # server  
        self.assertEqual(self.work_generator.triplestore_url,
                         "http://localhost:9999/blazegraph/sparql")

    def test__add_creators__(self):
        self.work_generator.__add_creators__(new_graph(), None, self.instance_uri)

    #def test__add_creators__

    def test__work_title__(self):
        self.work_generator.__add_work_title__(new_graph(), None, self.instance_uri)

    def test__raise_assert_error_copy_instance_to_work__(self):
        with self.assertRaises(AssertionError):
            self.work_generator.__copy_instance_to_work__(self.instance_uri, 
                None)

    def test__raise_error_copy_instance_to_work__(self):
        with self.assertRaises(ValueError):
            self.work_generator.__copy_instance_to_work__(
                self.instance_uri, 
                self.instance_uri)

    def test__generate_work__(self):
        self.assertIsNotNone(
            self.work_generator.__generate_work__(
                self.instance_uri))

    def test__similiar_creators__(self):
        self.work_generator.__similar_creators__(
            str(self.instance_uri))
        self.assertEqual(
            self.work_generator.matched_works,
            [])


    def test__similiar_titles__(self):
        self.work_generator.__similar_titles__(str(self.instance_uri))
        self.assertEqual(
            self.work_generator.matched_works,
            [])



    def test_harvest_instances(self):
        self.work_generator.harvest_instances()
        self.assertEqual(
            self.work_generator.matched_works,
            [])


    def test_run(self):
        self.work_generator.run()
        self.assertEqual(
            self.work_generator.matched_works,
            [])

class TestSuccessWorkGenerator(unittest.TestCase):

    def setUp(self):
        self.found_work = rdflib.URIRef("http://bibcat.org/TestWork-1234")
        self.work_generator = WorkGenerator()

    def test_run(self):
        found_response = MockResponse()
        found_response.output['results']['bindings'].append(
            {"instance": {"value": str(self.found_work)}})
        requests.post = MagicMock(return_value=found_response)
        self.work_generator.run()

        self.assertEqual(
            self.work_generator.matched_works,
            [])
        


if __name__ == '__main__':
    unittest.main()
        
