import os
import sys
import unittest
sys.path.append(os.path.abspath(os.path.curdir))
from generators.work import WorkGenerator

class TestWorkGenerator(unittest.TestCase):

    def setUp(self):
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

    def test__generate_work__(self):
        self.assertIsNotNone(
            self.work_generator.__generate_work__(
                str(self.instance_uri)))

    def test__similiar_titles__(self):
        self.assertEqual(
            self.work_generator.__similiar_titles__(str(self.instance_uri)),
            [])

    def test_harvest_instances(self):
        self.work_generator.harvest_instances()

    def test_run(self):
        self.work_generator.run()

        



if __name__ == '__main__':
    unittest.main()
        
