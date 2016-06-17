import os
import sys
import unittest
sys.path.append(os.path.abspath(os.path.curdir))
import work_generator

class TestWorkGenerator(unittest.TestCase):

    def setUp(self):
        self.work_generator = work_generator.WorkGenerator()

    def test_init(self):
        self.assertTrue(
            isinstance(self.work_generator, 
                       work_generator.WorkGenerator))
        # Default Blazegraph triplestore runs on localhost through semantic
        # server  
        self.assertEqual(self.work_generator.triplestore_url,
                         "http://localhost:8080/blazegraph/sparql")



if __name__ == '__main__':
    unittest.main()
        
