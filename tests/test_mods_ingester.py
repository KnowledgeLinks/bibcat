import logging
import os
import rdflib
import requests
import sys
import unittest
import xml.etree.ElementTree as etree

sys.path.append(os.path.abspath(os.path.curdir))
import ingesters
import ingesters.mods as mods
from ingesters.ingester import NS_MGR

ingesters.ingester.MLOG_LVL = logging.CRITICAL
logging.getLogger("requests").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

SAMPLE_MODS = etree.XML("""<mods xmlns="http://www.loc.gov/mods/v3" 
 xmlns:mods="http://www.loc.gov/mods/v3" 
 xmlns:xlink="http://www.w3.org/1999/xlink" 
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <titleInfo>
    <title>Arthur J. Kew and Ida Rosalie Fursman </title>
  </titleInfo>
  <typeOfResource>mixed material</typeOfResource>
<name type="personal">
    <namePart>Kew, Arthur J.</namePart>
    <role>
      <roleTerm authority="marcrelator" type="text">creator</roleTerm>
    </role>
  </name>
  <name type="personal">
    <namePart>Fursman, Ida Rosalie</namePart>
    <role>
      <roleTerm authority="marcrelator" type="text">creator</roleTerm>
    </role>
  </name>
</mods>""")

CREATOR_XPATH = "mods:name[@type='personal']/mods:role[mods:roleTerm='creator']/../mods:namePart"

class TestMODS__handle_linked_pattern__(unittest.TestCase):

    def setUp(self):
        self.ingester = mods.MODSIngester(SAMPLE_MODS)
        self.entity = self.ingester.__generate_uri__()

    def test_exists(self):
        self.assertTrue(hasattr(self.ingester, "__handle_linked_pattern__"))

    def test_no_keywords(self):
        self.assertRaises(
            AttributeError,
            self.ingester.__handle_linked_pattern__)

    def test_creator_pattern(self):
        self.ingester.__handle_linked_pattern__(
            entity=self.entity,
            rule=rdflib.Literal(CREATOR_XPATH),
            destination_class=NS_MGR.bf.Person,
            destination_property=NS_MGR.schema.alternativeName,
            target_class=NS_MGR.bf.Instance,
            target_property=NS_MGR.relators.cre)
        self.assertEqual(len(self.ingester.graph), 4)

    def test_title_pattern(self):
        self.ingester.__handle_linked_pattern__(
            entity=self.entity,
            rule=rdflib.Literal("mods:titleInfo/mods:title"),
            destination_class=NS_MGR.bf.InstanceTitle,
            destination_property=NS_MGR.bf.mainTitle,
            target_class=NS_MGR.bf.Instance,
            target_property=NS_MGR.bf.title)
        print(self.ingester.graph.serialize(format='turtle').decode()) 

    def tearDown(self):
        self.ingester.graph.close()

class TestInitMODSIngester(unittest.TestCase):

    def setUp(self):
        self.ingester = mods.MODSIngester()

    def test_defaults(self):
        self.assertEqual(
            self.ingester.base_url,
            "http://bibcat.org/")
        self.assertEqual(
            len(self.ingester.graph),
            0)
        self.assertTrue(
            len(self.ingester.rules_graph) > 1)
        self.assertIsNone(self.ingester.source)
        self.assertEqual(
            self.ingester.triplestore_url,
            "http://localhost:8080/blazegraph/sparql")

class TestMODSUpdateDirectProperties(unittest.TestCase):

    def setUp(self):
        self.entity = rdflib.URIRef("http://test.org/entity/1")
        self.ingester = mods.MODSIngester()


    def test_default_method(self):
        self.ingester.update_direct_properties(
            NS_MGR.bf.Instance,
            self.entity)

class TestMODSUpdateLinkedClasses(unittest.TestCase):

    def setUp(self):
        self.entity = rdflib.URIRef("http://test.org/entity/1")
        self.ingester = mods.MODSIngester()

    def test_default_method(self):
        self.ingester.update_linked_classes(
            NS_MGR.bf.Item,
            self.entity)

class TestMODSUpdateOrderedLinkedClasses(unittest.TestCase):

    def setUp(self):
        self.entity = rdflib.URIRef("http://test.org/entity/1")
        self.ingester = mods.MODSIngester()
       
    def test_default_method(self):
        self.ingester.update_ordered_linked_classes(
            NS_MGR.bf.Item,
            self.entity)
       
if __name__ == '__main__':
    unittest.main()
