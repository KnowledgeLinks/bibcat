"""Python RDF Mapping Language Processor"""

__author__ = "Jeremy Nelson"

# Standard Python Modules
import datetime
import os
from types import SimpleNamespace

# 3rd party modules
import rdflib
import requests


BIBCAT_BASE = os.path.abspath(
    os.path.split(
        os.path.dirname(__file__))[0])
NS_MGR = SimpleNamespace()
PREFIX = None
try:
    VERSION_PATH = os.path.join(
        BIBCAT_BASE,
        "VERSION")
    with open(VERSION_PATH) as version:
        __version__ = version.read().strip()
except:
    __version__ = "unknown"

try:
    from lxml import etree
except ImportError:
    import xml.etree.ElementTree as etree

class Processor(object):
    """Base class for RDF Mapping Language Processors, child classes
    encapsulate different types of Data sources"""

    def __init__(self, rml_rules):
        global NS_MGR
        self.rml = rdflib.Graph()
        if isinstance(rml_rules, list):
            for rule in rml_rules:
                with open(rule) as file_obj:
                    raw_rule = file_obj.read()
                self.rml.parse(data=raw_rule,
                               format='turtle')
        elif isinstance(rml_rules, (rdflib.Graph, rdflib.ConjunctiveGraph)):
            self.rml = rml_rules
        elif os.path.exists(rml_rules):
            self.rml.parse(rml_rules, format='turtle')
        else:
            raise ValueError("Cannot handle rml_rules={0}".format(rml_rules))
        # Populate Namespaces Manager
        for prefix, namespace in self.rml.namespaces():
            setattr(NS_MGR, prefix, rdflib.Namespace(namespace))
        self.output, self.source, self.triplestore_url = None, None, None
        self.parents = set()
        self.constants = dict(version=__version__)
        self.triple_maps = dict()
        for row in self.rml.query(GET_TRIPLE_MAPS):
            triple_map_iri = row[0]
            map_key = str(triple_map_iri)
            self.triple_maps[map_key] = SimpleNamespace()
            self.triple_maps[map_key].logicalSource = \
                self.__logical_source__(triple_map_iri)
            self.triple_maps[map_key].subjectMap = \
                self.__subject_map__(triple_map_iri)
            self.triple_maps[map_key].predicateObjectMap = \
                self.__predicate_object_map__(triple_map_iri)

    def __deduplicate__(self):
        """Simple de-duplication of the subject based on the value
        and class of the subject_iri.

        """
        existing_iri = dict()
        for row in self.rml.query(DEDUP_RULE):
            class_, filter_pred = row
            for subj_iri in self.output.subjects(
                    predicate=NS_MGR.rdf.type,
                    object=class_):
                value = self.output.value(subject=subj_iri,
                                          predicate=filter_pred)
                if str(value) in existing_iri:
                    self.__replace_iri__(subj_iri,
                                         existing_iri[str(value)])
                else:
                    existing_iri[str(value)] = subj_iri
                # Now deduplicate if existing triplestore
                if not hasattr(self, "triplestore_url") or self.triplestore_url is None:
                    continue
                query = DEDUP_TRIPLESTORE.format(
                    class_,
                    filter_pred,
                    value)
                dedup_result = requests.post(
                    self.triplestore_url,
                    data={"query": query,
                          "format": "json"})
                if dedup_result.status_code > 399:
                    continue
                bindings = dedup_result.json().get('results').get('bindings')
                if len(bindings) > 0:
                    new_iri = rdflib.URIRef(
                        bindings[0].get('subj').get('value'))
                    self.__replace_iri__(existing_iri[value],
                                         new_iri)

    def __replace_iri__(self, src_iri, new_iri):
        """Method replaces all triples with an original IRI replaced with the
        equivalent triples using the new IRI.

        Parameters

        ----------
            src_iri : rdflib URIRef, Original or source IRI
            new_iri : rdflib.URIREf, New replacement IRI
        """
        # Replace predicate and objects
        for pred, obj in self.output.predicate_objects(subject=src_iri):
            self.output.remove((src_iri, pred, obj))
            self.output.add((new_iri, pred, obj))
        # Replace subject and predicates
        for subj, pred in self.output.subject_predicates(object=src_iri):
            self.output.remove((subj, pred, src_iri))
            self.output.add((subj, pred, new_iri))



    def __graph__(self):
        """Method returns a new graph with all of the namespaces in
        RML graph"""
        graph = rdflib.Graph(namespace_manager=self.rml.namespace_manager)
        return graph


    def __logical_source__(self, map_iri):
        logical_source = SimpleNamespace()
        logical_src_bnode = self.rml.value(
            subject=map_iri,
            predicate=NS_MGR.rml.logicalSource)
        if logical_src_bnode is None:
            return
        logical_source.source = self.rml.value(
            subject=logical_src_bnode,
	           predicate=NS_MGR.rml.source)
        logical_source.reference_formulations = [r for r in self.rml.objects(
            subject=logical_src_bnode,
            predicate=NS_MGR.rml.referenceFormulation)]
        logical_source.iterator = self.rml.value(
            subject=logical_src_bnode,
            predicate=NS_MGR.rml.iterator)
        query = self.rml.value(
            subject=logical_src_bnode,
            predicate=NS_MGR.rml.query)
        if query is not None:
            logical_source.query = query
        return logical_source

    def __subject_map__(self, map_iri):
        """Creates a SimpleNamespace for the TripleMap's subjectMap and
        populates properties from the RML RDF graph

        Args:

        -----
            map_iri: rdflib.URIRef,TripleMap IRI

        Returns:

        --------
            SimpleNamespace
        """
        subject_map = SimpleNamespace()
        subject_map_bnode = self.rml.value(
            subject=map_iri,
            predicate=NS_MGR.rr.subjectMap)
        if subject_map_bnode is None:
            return
        subject_map.class_ = self.rml.value(
            subject=subject_map_bnode,
            predicate=getattr(NS_MGR.rr, "class"))
        subject_map.template = self.rml.value(
            subject=subject_map_bnode,
            predicate=NS_MGR.rr.template)
        subject_map.termType = self.rml.value(
            subject=subject_map_bnode,
            predicate=NS_MGR.rr.termType)
        subject_map.deduplicate = self.rml.value(
            subject=subject_map_bnode,
            predicate=NS_MGR.kds.deduplicate)
        subject_map.reference = self.rml.value(
            subject=subject_map_bnode,
            predicate=NS_MGR.rr.reference)
        return subject_map

    def __predicate_object_map__(self, map_iri):
        """Iterates through rr:predicateObjectMaps for this TripleMap
        creating a SimpleNamespace for each triple map and assigning the
        constant, template, parentTripleMap, reference as properties.

        Args:

        -----
                map_iri:  rdflib.URIRef, TripleMap IRI

        Returns:

        --------
                list:  List of predicate_object Namespace objects
        """
        pred_obj_maps = []
        for pred_obj_map_bnode in self.rml.objects(
                subject=map_iri,
                predicate=NS_MGR.rr.predicateObjectMap):
            pred_obj_map = SimpleNamespace()
            pred_obj_map.predicate = self.rml.value(
                subject=pred_obj_map_bnode,
                predicate=NS_MGR.rr.predicate)
            obj_map_bnode = self.rml.value(
                subject=pred_obj_map_bnode,
                predicate=NS_MGR.rr.objectMap)
            if obj_map_bnode is None:
                continue
            pred_obj_map.constant = self.rml.value(
                subject=obj_map_bnode,
                predicate=NS_MGR.rr.constant)
            pred_obj_map.template = self.rml.value(
                subject=obj_map_bnode,
                predicate=NS_MGR.rr.template)
            pred_obj_map.parentTriplesMap = self.rml.value(
                subject=obj_map_bnode,
                predicate=NS_MGR.rr.parentTriplesMap)
            if pred_obj_map.parentTriplesMap is not None:
                self.parents.add(str(pred_obj_map.parentTriplesMap))
            pred_obj_map.reference = self.rml.value(
                subject=obj_map_bnode,
                predicate=NS_MGR.rr.reference)
            pred_obj_map.datatype = self.rml.value(
                subject=obj_map_bnode,
                predicate=NS_MGR.rr.datatype)
            pred_obj_map.query = self.rml.value(
                subject=obj_map_bnode,
                predicate=NS_MGR.rml.query)
            pred_obj_maps.append(pred_obj_map)
        return pred_obj_maps

    def generate_term(self, **kwargs):
        """Method generates a rdflib.Term based on kwargs"""
        term_map = kwargs.pop('term_map')
        if hasattr(term_map, "termType") and\
            term_map.termType == NS_MGR.rr.BlankNode:
            return rdflib.BNode()
        if not hasattr(term_map, 'datatype'):
            term_map.datatype = NS_MGR.xsd.anyURI
        if term_map.template is not None:
            template_vars = kwargs
            template_vars.update(self.constants)
            # Call any functions to generate values
            for key, value in template_vars.items():
                if hasattr(value, "__call__"):
                    template_vars[key] = value()
            raw_value = term_map.template.format(**template_vars)
            if term_map.datatype == NS_MGR.xsd.anyURI:
                return rdflib.URIRef(raw_value)
            return rdflib.Literal(raw_value,
                                  datatype=term_map.datatype)
        if term_map.reference is not None:
            # Each child will have different mechanisms for referencing the
            # source based
            return self.__generate_reference__(term_map, **kwargs)

    def execute(self, triple_map, **kwargs):
        """Placeholder method should be overridden by child classes"""
        pass

    def run(self, **kwargs):
        """Run method iterates through triple maps and calls the execute
        method"""
        if not 'timestamp' in kwargs:
            kwargs['timestamp'] = datetime.datetime.utcnow().isoformat()

        print("Parents are {}".format(self.parents))
        for map_key, triple_map in self.triple_maps.items():
            if map_key not in self.parents:
                self.execute(triple_map, **kwargs)
        # Post-processing
        self.__deduplicate__()

class CSVProcessor(Processor):
    """CSV RDF Mapping Processor"""

    def __init__(self, **kwargs):
        if "fields" in kwargs:
            self.fields = fields
        if "rml_rules" in kwargs:
            rml_rules = kwargs.pop("rml_rules")
        super(CSVProcessor, self).__init__(rml_rules)

    def execute(self, triple_map, **kwargs):
        """Method executes mapping between CSV source and
        output RDF

        args:
            triple_map(SimpleNamespace): Triple Map
        """

class XMLProcessor(Processor):
    """XML RDF Mapping Processor"""

    def __init__(self, **kwargs):
        if "rml_rules" in kwargs:
            rml_rules = kwargs.pop("rml_rules")
        super(XMLProcessor, self).__init__(rml_rules)
        if "namespaces" in kwargs:
            self.xml_ns = kwargs.pop("namespaces")
        else:
            self.xml_ns = dict()
        self.constants.update(kwargs)

    def __generate_reference__(self, triple_map, **kwargs):
        """Internal method takes a triple_map and returns the result of 
        applying to XPath to the current DOM context

        Args:
        -----
            triple_map: SimpleNamespace 
            element: etree.Element
        """
        element = kwargs.get("element")
        found_elements = element.findall(triple_map.reference, self.xml_ns)
        for elem in found_elements:
            #! Quick and dirty test for valid URI
            if not elem.text.startswith("http"):
                continue
            return rdflib.URIRef(elem.text)
            

    def execute(self, triple_map, **kwargs):
        """Method executes mapping between source

        Args:

        -----
            triple_map: SimpleNamespace, Triple Map

        """
        subjects = []
        for element in self.source.findall(
                str(triple_map.logicalSource.iterator),
                self.xml_ns):
            subject = self.generate_term(term_map=triple_map.subjectMap,
                                         element=element,
                                         **kwargs)
            start = len(self.output)
            for row in triple_map.predicateObjectMap:
                predicate = row.predicate
                if row.template is not None:
                    self.output.add((
                        subject,
                        predicate,
                        self.generate_term(term_map=row, **kwargs)))
                if row.parentTriplesMap is not None:
                    parent_objects = self.execute(
                        self.triple_maps[str(row.parentTriplesMap)],
                        **kwargs)
                    for parent_obj in parent_objects:
                        self.output.add((
                            subject,
                            predicate,
                            parent_obj))
                if row.reference is not None:
                    found_elements = element.findall(str(row.reference),
                                                     self.xml_ns)
                    for found_elem in found_elements:
                        if found_elem.text is None or len(found_elem.text) < 1:
                            if row.constant is not None:
                                self.output.add((subject,
                                                 predicate,
                                                 row.constant))
                            continue

                        if hasattr(row, 'datatype') and \
                           row.datatype is not None:
                            if row.datatype == NS_MGR.xsd.anyURI:
                                ref_obj = rdflib.URIRef(found_elem.text)
                            else:
                                ref_obj = rdflib.Literal(
                                    found_elem.text,
                                    datatype=row.datatype)
                        else:
                            ref_obj = rdflib.Literal(found_elem.text)
                        self.output.add((subject,
                                         predicate,
                                         ref_obj))
                elif row.constant is not None:
                    self.output.add((subject,
                                     predicate,
                                     row.constant))
            if start < len(self.output):
                if triple_map.subjectMap.class_ is not None:
                    self.output.add((subject,
                                     NS_MGR.rdf.type,
                                     triple_map.subjectMap.class_))
            subjects.append(subject)
        return subjects



    def run(self, xml, **kwargs):
        self.output = self.__graph__()
        if isinstance(xml, str):
            self.source = etree.XML(xml)
        else:
            self.source = xml
        super(XMLProcessor, self).run(**kwargs)


def __get_object__(binding):
    """Method takes a binding extracts value and returns rdflib
     entity

     Args:
         binding: binding row
    """
    for row in binding.values():
        if row.get('type').startswith('uri'):
            yield rdflib.URIRef(row.get('value'))
        if row.get('type').startswith('literal'):
            yield rdflib.Literal(row.get('value'))


class SPARQLProcessor(Processor):
    """SPARQLProcessor provides a RML Processor for external SPARQL endpoints"""

    def __init__(self, **kwargs):
        if "rml_rules" in kwargs:
            rml_rules = kwargs.pop("rml_rules")
        super(SPARQLProcessor, self).__init__(rml_rules)
        __set_prefix__()
        # Defaults to Blazegraph, don't really like.
        self.triplestore_url = kwargs.get(
            "triplestore_url",
            "http://localhost:9999/blazegraph/sparql")
        # Sets defaults
        self.limit, self.offset = 5000, 0



    def run(self, **kwargs):
        self.output = self.__graph__()
        if "limit" in kwargs:
            self.limit = kwargs.get('limit')
        if "offset" in kwargs:
            self.offset = kwargs.get('offset')
        super(SPARQLProcessor, self).run(**kwargs)

    def execute(self, triple_map, **kwargs):
        """Execute """
        subjects = []
        if NS_MGR.ql.JSON in triple_map.logicalSource.reference_formulations:
            output_format = "json"
        else:
            output_format = "xml"
        iterator = str(triple_map.logicalSource.iterator)
        if not 'limit' in kwargs:
            kwargs['limit'] = self.limit
        if not 'offset' in kwargs:
            kwargs['offset'] = self.offset
        sparql = PREFIX + triple_map.logicalSource.query.format(
            **kwargs)
        result = requests.post(
            self.triplestore_url,
            data={"query": sparql,
                  "format": output_format})
        if output_format == "json":
            bindings = result.json().get("results").get("bindings")
        elif output_format == "xml":
            xml_doc = etree.XML(result.text)
            bindings = xml_doc.findall("results/bindings")
        iterator = str(triple_map.logicalSource.iterator)
        for binding in bindings:
            entity = rdflib.URIRef(binding.get(iterator).get('value'))
            if triple_map.subjectMap.class_ is not None:
                self.output.add((entity,
                                 NS_MGR.rdf.type,
                                 triple_map.subjectMap.class_))
            for pred_obj_map in triple_map.predicateObjectMap:
                predicate = pred_obj_map.predicate
                if pred_obj_map.parentTriplesMap is not None:
                    parent_objects = self.execute(
                        self.triple_maps[str(pred_obj_map.parentTriplesMap)],
                        **kwargs)
                    for parent_obj in parent_objects:
                        self.output.add((
                            entity,
                            predicate,
                            parent_obj))
                    continue
                sparql_query = PREFIX + pred_obj_map.query.format(
                    **{iterator: entity})
                result = requests.post(
                    self.triplestore_url,
                    data={"query": sparql_query,
                          "format": output_format})
                if output_format.startswith("json"):
                    pre_obj_bindings = result.json().get(
                        'results').get('bindings')
                    for row in pre_obj_bindings:
                        for object_ in __get_object__(row):
                            self.output.add((entity, predicate, object_))
            subjects.append(entity)
        return subjects


def __set_prefix__():
    global PREFIX
    PREFIX = ""
    for row in dir(NS_MGR):
        if row.startswith("__") or row is None:
            continue
        PREFIX += "PREFIX {0}: <{1}>\n".format(row, getattr(NS_MGR, row))
    return PREFIX

__set_prefix__()
DEDUP_RULE = PREFIX + """
SELECT DISTINCT ?class ?bf_match
WHERE {
   ?map rr:subjectMap ?sub_map .
   ?sub_map rr:class ?class .
   ?sub_map kds:deduplicate ?bf_match
}"""


DEDUP_TRIPLESTORE = PREFIX + """
SELECT DISTINCT ?subj
WHERE {{
    ?subj rdf:type <{0}> .
    ?subj <{1}> ?name .
    FILTER(CONTAINS(?name, \"""{2}\"""))
}}"""


GET_TRIPLE_MAPS = PREFIX + """
SELECT DISTINCT ?map
WHERE {
    ?map rdf:type rr:TriplesMap .
}"""
