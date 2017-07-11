"""Python RDF Mapping Language Processor

>>> import bibcat.rml.processor as processor

"""

__author__ = "Jeremy Nelson"

# Standard Python Modules
import collections
import datetime
import json
import os
from types import SimpleNamespace

# 3rd party modules
import bibcat
import rdflib
import requests

import jsonpath_ng
from bibcat.maps import get_map

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
except FileNotFoundError:
    __version__ = "unknown"

try:
    from lxml import etree
except ImportError:
    import xml.etree.ElementTree as etree

class Processor(object):
    """Base class for RDF Mapping Language Processors, child classes
    encapsulate different types of Data sources


    """

    def __init__(self, rml_rules):
        self.rml = rdflib.Graph()
        if isinstance(rml_rules, list):
            for rule in rml_rules:
                # First check if rule exists on the filesystem
                if os.path.exists(rule):
                    with open(rule) as file_obj:
                        raw_rule = file_obj.read()
                else:
                    raw_rule = get_map(rule).decode()
                self.rml.parse(data=raw_rule,
                               format='turtle')
        elif isinstance(rml_rules, (rdflib.Graph, rdflib.ConjunctiveGraph)):
            self.rml = rml_rules
        elif os.path.exists(rml_rules):
            self.rml.parse(rml_rules, format='turtle')
        else:
            self.rml.parse(data=get_map(rml_rules).decode(), format='turtle')
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

    def __graph__(self):
        """Method returns a new graph with all of the namespaces in
        RML graph"""
        graph = rdflib.Graph(namespace_manager=self.rml.namespace_manager)
        return graph



    def __generate_delimited_objects__(self, **kwargs):
        """Internal methods takes a subject, predicate, element, and a list
        of delimiters that are applied to element's text and a triples
        for each value is created and associated with the subject.

        Keyword Args:

        -------------
            triple_map: SimpleNamespace
            predicate: URIRef
            element: XML Element
            datatype: XSD Datatype, optional
            delimiters: List of delimiters to apply to string
        """
        triple_map = kwargs.get("triple_map")
        subject = kwargs.get('subject')
        # Subject is blank-node, try to retrieve subject IRI
        predicate = kwargs.get('predicate')
        element = kwargs.get('element')
        datatype = kwargs.get('datatype', None)
        delimiters = kwargs.get('delimiters')
        subjects = []
        for delimiter in delimiters:
            values = element.text.split(delimiter)
            for row in values:
                if datatype is not None:
                    obj_ = rdflib.Literal(row.strip(), datatype=datatype)
                else:
                    obj_ = rdflib.Literal(row.strip())
                if isinstance(subject, rdflib.BNode):
                    new_subject = rdflib.BNode()
                    class_ = triple_map.subjectMap.class_
                    self.output.add((new_subject, NS_MGR.rdf.type, class_))
                    for parent_subject, parent_predicate in self.output.subject_predicates(
                            object=subject):
                        self.output.add((parent_subject, parent_predicate, new_subject))
                else:
                    new_subject = subject
                subjects.append(new_subject)
                self.output.add((new_subject, predicate, obj_))
        return subjects

    def __generate_reference__(self, triple_map, **kwargs):
        """Placeholder method, should be extended by child classes

        Args:

        -----
            triple_map: SimpleNamespace

        Keyword Args:

        -------------
        """
        pass

    def __generate_object_term__(self, datatype, value):
        """Internal method takes a datatype (can be None) and returns
        the RDF Object Term

        Args:

        -----
            datatype: None, or rdflib.URIRef
            value: Varys depending on ingester
        """
        if datatype == NS_MGR.xsd.anyURI:
            term = rdflib.URIRef(value)
        elif datatype:
            term = rdflib.Literal(value, datatype=datatype)
        else:
            term = rdflib.Literal(value)
        return term

    def __handle_parents__(self, **kwargs):
        """Internal method handles parentTriplesMaps

        Keyword args:

        -------------

            parent_map: SimpleNamespace of ParentTriplesMap
            subject: rdflib.URIRef or rdflib.BNode
            predicate: rdflib.URIRef
        """
        parent_map = kwargs.pop("parent_map")
        subject = kwargs.pop('subject')
        predicate = kwargs.pop('predicate')
        parent_objects = self.execute(
            self.triple_maps[str(parent_map)],
            **kwargs)
        for parent_obj in parent_objects:
            self.output.add((
                subject,
                predicate,
                parent_obj))

    def __logical_source__(self, map_iri):
        """Creates a SimpleNamespace for the TripelMap's logicalSource

        Args:

        -----
            map_iri: URIRef
        """
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
        #! Should look at supporting multple rr:class definitions
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
            # BIBCAT Extensions
            pred_obj_map.delimiters = []
            for obj in self.rml.objects(subject=obj_map_bnode,
                                        predicate=NS_MGR.kds.delimiter):
                pred_obj_map.delimiters.append(obj)
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
        if 'timestamp' not in kwargs:
            kwargs['timestamp'] = datetime.datetime.utcnow().isoformat()
        if 'version' not in kwargs:
            kwargs['version'] = bibcat.__version__
        for map_key, triple_map in self.triple_maps.items():
            if map_key not in self.parents:
                self.execute(triple_map, **kwargs)
        
class CSVProcessor(Processor):
    """CSV RDF Mapping Processor"""

    def __init__(self, **kwargs):
        if "fields" in kwargs:
            self.fields = kwargs.pop("fields")
        if "rml_rules" in kwargs:
            rml_rules = kwargs.pop("rml_rules")
        super(CSVProcessor, self).__init__(rml_rules)

    def __generate_reference__(self, triple_map, **kwargs):
        """Extracts the value of either column by key or by position """
        pass

    def execute(self, triple_map, **kwargs):
        """Method executes mapping between CSV source and
        output RDF

        args:
            triple_map(SimpleNamespace): Triple Map
        """
        pass

    def run(self, csv_file, **kwargs):
        """Method takes either path to the CSV file, csv.Reader 
        or a csv.DictReader instance and iterates through mappings

        
        Args:

        -----
            csv_file: str, csv.DictReader
        """

class JSONProcessor(Processor):
    """JSON RDF Mapping Processor"""

    def __init__(self, **kwargs):
        try:
            rml_rules = kwargs.pop("rml_rules")
        except KeyError:
            rml_rules = []
        super(JSONProcessor, self).__init__(rml_rules)

    def __generate_reference__(self,  triple_map, **kwargs):
        json_obj = kwargs.get("obj")
        path_expr = jsonpath_ng.parse(triple_map.reference)
        results = [r.value for r in path_expr.find(json_obj)]
        for row in results:
            if rdflib.term._is_valid_uri(row):
                return rdflib.URIRef(row)

    def __reference_handler__(self, **kwargs):
        """Internal method for handling rr:reference in triples map

        Keyword Args:

        -------------
            predicate_obj_map: SimpleNamespace
            obj: dict
            subject: rdflib.URIRef
        """
        subjects = []
        pred_obj_map = kwargs.get("predicate_obj_map")
        element = kwargs.get("obj")
        subject = kwargs.get("subject")
        if pred_obj_map.reference is None:
            return subjects
        predicate = pred_obj_map.predicate
        ref_exp = jsonpath_ng.parse(str(pred_obj_map.refernce))
        found_objects = [r.value for r in ref_exp(obj)]
        for row in found_objects:
            self.output.append(subject, predicate, rdflib.Literal(row))
            
 
    def execute(self, triple_map, **kwargs):
        """Method executes mapping between JSON source and
        output RDF

        Args:

        -----
            triple_map: SimpleNamespace
        """
        subjects = []
        logical_src_iterator = str(triple_map.logicalSource.iterator)
        json_object = kwargs.get('obj', self.source)
        # Removes '.' as a generic iterator, replace with '@'
        if logical_src_iterator == ".":
            results = [None,]
        else:
            json_path_exp = jsonpath_ng.parse(logical_src_iterator)
            results = [r.value for r in json_path_exp.find(json_object)][0]
        for row in results:
            subject = self.generate_term(term_map=triple_map.subjectMap,
                                         obj=row,
                                         **kwargs)
            for pred_obj_map in triple_map.predicateObjectMap:
                predicate = pred_obj_map.predicate
                if pred_obj_map.template is not None:
                    self.output.add((
                        subject,
                        predicate,
                        self.generate_term(term_map=pred_obj_map, **kwargs)))
                
                if pred_obj_map.parentTriplesMap is not None:
                    self.__handle_parents__(
                        parent_map=pred_obj_map.parentTriplesMap,
                        subject=subject,
                        predicate=predicate,
                        **kwargs)
                if pred_obj_map.reference is not None:
                    ref_exp = jsonpath_ng.parse(str(pred_obj_map.reference))
                    found_objects = [r.value for r in ref_exp.parse(row)]
                    for obj in found_objects:
                        if rdflib.term._is_valid_uri(obj):
                            rdf_obj = rdflib.URIRef(str(obj))
                        else:
                            rdf_obj = rdflib.Literal(str(obj))
                        self.output.add((subject, predicate, ref_obj))
                if pred_obj_map.constant is not None:
                    self.output.add((subject,
                                     predicate,
                                     pred_obj_map.constant))
            subjects.append(subject)
        return subjects
            
        


    def run(self, source, **kwargs):
        """Method takes a JSON source and any keywords and transforms from
        JSON to Lean BIBFRAME 2.0 triples

        Args:

        ----
            source: str, dict
        """
        self.output = self.__graph__()
        if isinstance(source, str):
            import json
            source = json.loads(source)
        self.source = source
        super(JSONProcessor, self).run(**kwargs)
        

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


    def __reference_handler__(self, **kwargs):
        """Internal method for handling rr:reference in triples map

        Keyword Args:

        -------------
            predicate_obj_map: SimpleNamespace
            element: etree.Element
            subject: rdflib.URIRef
        """
        subjects = []
        pred_obj_map = kwargs.get("predicate_obj_map")
        element = kwargs.get("element")
        subject = kwargs.get("subject")
        if pred_obj_map.reference is None:
            return subjects
        predicate = pred_obj_map.predicate
        found_elements = element.findall(str(pred_obj_map.reference),
                                         self.xml_ns)
        for found_elem in found_elements:
            if found_elem.text is None or len(found_elem.text) < 1:
                continue
            if pred_obj_map.constant is not None:
                self.output.add((subject,
                                 predicate,
                                 pred_obj_map.constant))
                continue
            if not hasattr(pred_obj_map, "datatype") or \
                pred_obj_map.datatype is None:
                datatype = None
            else:
                datatype = pred_obj_map.datatype
            if pred_obj_map.delimiters != []:
               subjects.extend(
                    self.__generate_delimited_objects__(
                        triple_map=pred_obj_map,
                        subject=subject,
                        predicate=predicate,
                        element=found_elem,
                        delimiters=pred_obj_map.delimiters,
                        datatype=datatype))
            else:
                object_ = self.__generate_object_term__(datatype, found_elem.text)
                self.output.add((subject, predicate, object_))
        return subjects


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
                    self.__handle_parents__(
                        parent_map=row.parentTriplesMap,
                        subject=subject,
                        predicate=predicate,
                        **kwargs)
                subjects.extend(self.__reference_handler__(
                    predicate_obj_map=row,
                    element=element,
                    subject=subject))
                if row.constant is not None:
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
    if isinstance(binding, rdflib.term.Node):
        return binding
    elif isinstance(binding, collections.Iterable):
        for row in binding.values():
            if isinstance(row, (rdflib.URIRef, rdflib.Literal)):
                return row
            elif isinstance(row, str):
                return rdflib.Literal(row)
            elif row.get('type').startswith('uri'):
                return rdflib.URIRef(row.get('value'))
            elif row.get('type').startswith('literal'):
                return rdflib.Literal(row.get('value'))


class SPARQLProcessor(Processor):
    """SPARQLProcessor provides a RML Processor for external SPARQL endpoints"""

    def __init__(self, **kwargs):
        if "rml_rules" in kwargs:
            rml_rules = kwargs.pop("rml_rules")
        super(SPARQLProcessor, self).__init__(rml_rules)
        __set_prefix__()
        self.triplestore_url = kwargs.get("triplestore_url")
        if self.triplestore_url is None:
            # Tries using rdflib Graph as triplestore
            self.triplestore = kwargs.get("triplestore", self.__graph__())

        # Sets defaults
        self.limit, self.offset = 5000, 0

    def __get_bindings__(self, sparql, output_format):
        """Internal method queries triplestore or remote
        sparal endpont and returns the bindings

        Args:

        ----
            sparql: String of SPARQL query
            output_format: String of type of outputform
        """
        if self.triplestore_url is None:
            result = self.triplestore.query(sparql)
            bindings = result.bindings
        else:
            result = requests.post(
                self.triplestore_url,
                data={"query": sparql,
                      "format": output_format})
            if output_format == "json":
                bindings = result.json().get("results").get("bindings")
            elif output_format == "xml":
                xml_doc = etree.XML(result.text)
                bindings = xml_doc.findall("results/bindings")
        return bindings

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
        if 'limit' not in kwargs:
            kwargs['limit'] = self.limit
        if 'offset' not in kwargs:
            kwargs['offset'] = self.offset
        iterator = str(triple_map.logicalSource.iterator)
        sparql = PREFIX + triple_map.logicalSource.query.format(
            **kwargs)
        bindings = self.__get_bindings__(sparql, output_format)
        for binding in bindings:
            entity_raw = binding.get(iterator)
            if isinstance(entity_raw, (rdflib.URIRef, rdflib.BNode)):
                entity = entity_raw
            else:
                entity = rdflib.URIRef(entity_raw.get('value'))
            if triple_map.subjectMap.class_ is not None:
                self.output.add((entity,
                                 NS_MGR.rdf.type,
                                 triple_map.subjectMap.class_))
            for pred_obj_map in triple_map.predicateObjectMap:
                predicate = pred_obj_map.predicate
                kwargs[iterator] = entity

                if pred_obj_map.parentTriplesMap is not None:
                    self.__handle_parents__(
                        parent_map=pred_obj_map.parentTriplesMap,
                        subject=entity,
                        predicate=predicate,
                        **kwargs)
                    continue
                if pred_obj_map.reference is not None:
                    ref_key = str(pred_obj_map.reference)
                    if ref_key in binding:
                        object_ = __get_object__(
                            binding[ref_key])
                        self.output.add((entity, predicate, object_))
                    continue
                if pred_obj_map.constant is not None:
                    self.output.add(
                        (entity, predicate, pred_obj_map.constant))
                    continue
                sparql_query = PREFIX + pred_obj_map.query.format(
                    **kwargs)
                pre_obj_bindings = self.__get_bindings__(
                    sparql_query,
                    output_format)
                for row in pre_obj_bindings:
                    object_ = __get_object__(row)
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

PREFIX = __set_prefix__()

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
