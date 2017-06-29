import logging
import os
import rdflib
import requests
import sys
import unittest
import xml.etree.ElementTree as etree

sys.path.append(os.path.abspath(os.path.curdir))
BIBCAT_BASE = os.path.abspath(
    os.path.split(
        os.path.dirname(__file__))[0])
PROJECT_BASE = os.path.split(BIBCAT_BASE)[0]
sys.path.append(PROJECT_BASE)
try:
    from instance import config
except ModuleNotFoundError:
    class Config(object):
        def __init__(self):
            self.BASE_URL = "http://bibcat.org/"
            self.TRIPLESTORE_URL = "http://localhost:9999/blazegraph/sparql"
    config = Config()
import ingesters
import ingesters.mods as mods
from ingesters.ingester import Ingester, NS_MGR

ingesters.MLOG_LVL = logging.CRITICAL
logging.getLogger("requests").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

SAMPLE_MODS = etree.XML("""<mods xmlns="http://www.loc.gov/mods/v3" 
 xmlns:mods="http://www.loc.gov/mods/v3" 
 xmlns:xlink="http://www.w3.org/1999/xlink" 
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <titleInfo>
    <title>Arthur J. Kew and Ida Rosalie Fursman</title>
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
  <genre authority="marcgt">letter</genre>
  <genre authority="marcgt">picture</genre>
  <location><url>http://example.edu/1234</url></location>
</mods>""")

SAMPLE_MODS_THESIS = etree.XML("""<mods xmlns="http://www.loc.gov/mods/v3" 
 xmlns:mods="http://www.loc.gov/mods/v3" 
 xmlns:xlink="http://www.w3.org/1999/xlink" 
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <titleInfo>
        <title>Sirena Selena, Queen of Dreams: A Responsible Translation of Difference and Unspoken Rhetorics</title>
    </titleInfo>
    <genre authority="marcgt">thesis</genre>
    <name type="corporate">
        <namePart>Colorado College</namePart>
        <role>
            <roleTerm type="text" authority="marcrt">degree grantor</roleTerm>
        </role>
    </name>
</mods>""")

CREATOR_XPATH = "mods:name[@type='personal']/mods:role[mods:roleTerm='creator']/../mods:namePart"
SELECT_GENRES = NS_MGR.prefix() + """
SELECT ?genre
WHERE {
    ?subj rdf:type bf:GenreForm .
    ?subj rdf:value ?genre .
}"""

SELECT_ORG_LABEL = NS_MGR.prefix() + """
SELECT ?label 
WHERE {
    ?subj rdf:type bf:Organization .
    ?subj rdfs:label ?label .
}"""

class TestMODS__handle_linked_pattern__(unittest.TestCase):

    def setUp(self):
        self.ingester = mods.MODSIngester(source=SAMPLE_MODS)
        self.entity = self.ingester.__generate_uri__()

    def test_exists(self):
        self.assertTrue(hasattr(self.ingester, "__handle_linked_pattern__"))

    def test_no_keywords(self):
        self.assertIsNone(self.ingester.__handle_linked_pattern__())


    def test_creator_pattern(self):
        self.ingester.__handle_linked_pattern__(
            entity=self.entity,
            rule=rdflib.Literal(CREATOR_XPATH),
            destination_class=NS_MGR.bf.Person,
            destination_property=NS_MGR.schema.alternativeName,
            target_class=NS_MGR.bf.Instance,
            target_property=NS_MGR.relators.cre)
        self.assertEqual(len(self.ingester.graph), 4)

    def test_genre_pattern(self):
        self.ingester.__handle_linked_pattern__(
            entity=self.entity,
            rule=rdflib.Literal("mods:genre[@authority='marcgt']"),
            destination_class=NS_MGR.bf.GenreForm,
            destination_property=NS_MGR.rdf.value,
            target_class=NS_MGR.bf.Instance,
            target_property=NS_MGR.bf.genreForm)
        genres = []
        for row in self.ingester.graph.query(SELECT_GENRES):
            genres.append(str(row[0]))
        self.assertListEqual(sorted(genres),
            ["letter", "picture"])
                 

    def test_title_pattern(self):
        self.ingester.__handle_linked_pattern__(
            entity=self.entity,
            rule=rdflib.Literal("mods:titleInfo/mods:title"),
            destination_class=NS_MGR.bf.InstanceTitle,
            destination_property=NS_MGR.bf.mainTitle,
            target_class=NS_MGR.bf.Instance,
            target_property=NS_MGR.bf.title)
        title = None
        for row in self.ingester.graph.objects(predicate=NS_MGR.bf.mainTitle):
            title = row
        self.assertEqual(
            str(title),
            "Arthur J. Kew and Ida Rosalie Fursman")

    def tearDown(self):
        self.ingester.graph.close()


class Test__handle_linked_bnode__(unittest.TestCase):

    def setUp(self):
        self.ingester = mods.MODSIngester(source=SAMPLE_MODS_THESIS)
        self.entity = self.ingester.__generate_uri__()

    def test_exists(self):
        self.assertTrue(hasattr(self.ingester, "__handle_linked_bnode__"))

    def test_degreeGrantor(self):
        degree_grantor = getattr(NS_MGR.bc, "mods-degreeGrantor")
        degree_grantor_bnode = self.ingester.rules_graph.value(
            subject=degree_grantor,
            predicate=NS_MGR.kds.destPropUri)
        self.ingester.__handle_linked_bnode__(
            entity=self.entity,
            bnode=degree_grantor_bnode,
            destination_class=NS_MGR.bf.Dissertation,
            target_property=NS_MGR.bf.dissertation,
            target_subject=degree_grantor)
        org_labels = []
        for row in self.ingester.graph.query(SELECT_ORG_LABEL):
            org_labels.append(str(row[0]))
        self.assertEqual(
            org_labels[0],
            "Colorado College")
            
    def test_no_keywords(self):
        pass

       
    def tearDown(self):
        self.ingester.graph.close()
       

class Test__handle_pattern__(unittest.TestCase):

    def setUp(self):
        self.ingester = mods.MODSIngester(source=SAMPLE_MODS)
        self.entity = self.ingester.__generate_uri__()
        self.cc = rdflib.URIRef("http://coloradocollege.edu/")
        bc_org = getattr(NS_MGR.kds, "bf-Organization")
        self.ingester.rules_graph.add((
            bc_org,
            NS_MGR.rdf.type,
            NS_MGR.kds.PropertyLinker))
        self.held_by = rdflib.BNode()
        self.ingester.rules_graph.add((
            bc_org,
            NS_MGR.kds.destPropUri,
            self.held_by))
        self.ingester.rules_graph.add((
            self.held_by,
            NS_MGR.bf.heldBy,
            self.cc))
        self.ingester.rules_graph.add((
            bc_org,
            NS_MGR.kds.destClassUri,
            NS_MGR.bf.Item)) 
            

    def test_exists(self):
        self.assertTrue(
            hasattr(self.ingester,
                    '__handle_pattern__'))

    def test_location_url(self):
        self.ingester.__handle_pattern__(
            self.entity,
            rdflib.Literal("mods:location/mods:url"),
            NS_MGR.schema.url)
        self.assertEqual(
            str(self.ingester.graph.value(subject=self.entity,
                predicate=NS_MGR.schema.url)),
            "http://example.edu/1234")

    def test_add_org_item(self):
        self.ingester.graph.add((
            self.entity,
            NS_MGR.rdf.type,
            NS_MGR.bf.Item))
        self.ingester.__handle_pattern__(
            self.entity,
            None,
            self.held_by)
        self.assertEqual(
            self.ingester.graph.value(subject=self.entity,
                predicate=NS_MGR.bf.heldBy),
            self.cc)

    def test_no_args(self):
        self.assertRaises(
            TypeError,
            self.ingester.__handle_pattern__)
        

    def tearDown(self):
        self.ingester.rules_graph.close()

class TestInitMODSIngester(unittest.TestCase):

    def setUp(self):
        self.ingester = mods.MODSIngester()

    def test_defaults(self):
        if hasattr(config, "BASE_URL"):
            self.assertEqual(
                self.ingester.base_url,
                config.BASE_URL)
        self.assertEqual(
            len(self.ingester.graph),
            0)
        self.assertTrue(
            len(self.ingester.rules_graph) > 1)
        self.assertIsNone(self.ingester.source)
        self.assertIn(
            self.ingester.triplestore_url,
            ['http://localhost:9999/blazegraph/sparql',
             config.TRIPLESTORE_URL])

    def tearDown(self):
        self.ingester.graph.close()


class TestMODSUpdateDirectProperties(unittest.TestCase):

    def setUp(self):
        self.entity = rdflib.URIRef("http://test.org/entity/1")
        self.ingester = mods.MODSIngester()


    def test_default_method(self):
        self.ingester.update_direct_properties(
            NS_MGR.bf.Instance,
            self.entity)

    def tearDown(self):
        self.ingester.graph.close()


class TestMODSUpdateLinkedClasses(unittest.TestCase):

    def setUp(self):
        self.entity = rdflib.URIRef("http://test.org/entity/1")
        self.ingester = mods.MODSIngester()

    def test_default_method(self):
        self.ingester.update_linked_classes(
            NS_MGR.bf.Item,
            self.entity)

    def tearDown(self):
        self.ingester.graph.close()


class TestMODSUpdateOrderedLinkedClasses(unittest.TestCase):

    def setUp(self):
        self.entity = rdflib.URIRef("http://test.org/entity/1")
        self.ingester = mods.MODSIngester()
       
    def test_default_method(self):
        self.ingester.update_ordered_linked_classes(
            NS_MGR.bf.Item,
            self.entity)

    def tearDown(self):
        self.ingester.graph.close()


class TestDeduplicateAgents(unittest.TestCase):

    def setUp(self):
        self.ingester = mods.MODSIngester(source=SAMPLE_MODS)
        self.entity =  self.ingester.__generate_uri__()

    def test_defaults_no_transform(self):
        self.assertEqual(len(self.ingester.graph), 0)
        self.ingester.deduplicate_agents(None, None)
        self.assertEqual(len(self.ingester.graph), 0)

    #! NEED to mock triplestore 
    def test_defaults_transform(self):
        self.ingester.transform()
        

    def tearDown(self):
        self.ingester.rules_graph.close()

if __name__ == '__main__':
    unittest.main()
