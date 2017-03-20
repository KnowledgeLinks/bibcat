__author__ = "Jeremy Nelson"

import datetime
import os
import rdflib
import sys
import uuid
from types import SimpleNamespace

NS_MGR = SimpleNamespace()
    
BIBCAT_BASE = os.path.abspath(
    os.path.split(
        os.path.dirname(__file__))[0])
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

    def __init__(self, rml_rules):
        global NS_MGR
        self.rml = rdflib.Graph()
        self.rml.parse(rml_rules, format='turtle')
        # Parse BIBCAT RML Base
        self.rml.parse(os.path.join(BIBCAT_BASE, 
            os.path.join("rdfw-definitions", "rml-bibcat-base.ttl")),
            format='turtle')
        # Populate Namespaces Manager 
        for prefix, namespace in self.rml.namespaces():
            setattr(NS_MGR, prefix, rdflib.Namespace(namespace))
        self.output, self.source = None, None
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

    def __deduplicate__(self, subject_map, subject_iri, value):
        """Simple de-duplication of the subject based on the value
        and class of the subject_iri.

        Args:
            subject_map: Triple Map's Subject Map 
            subject_iri(rdflib.URIRef): Current Subject IRI
            value(rdflib.Literal): Value from Triple Map 
        """
        predicate = subject_map.deduplicate
        for existing_subject in set([s for s in self.output.subjects(predicate=predicate,
             object=value)]):
            if subject_map.class_ in set([str(obj) for obj in self.output.objects(
                subject=existing_subject,
                predicate=NS_MGR.rdf.type)]):
                # Matched Class and Property Value
                return existing_subject
        return subject_iri
                


    def __graph__(self):
        """Method returns a new graph with all of the namespaces in
        RML graph"""
        graph = rdflib.Graph(namespace_manager=self.rml.namespace_manager)
        return graph
            

    def __logical_source__(self, map_iri):
        logical_source = SimpleNamespace()
        logical_src_bnode = self.rml.value(subject=map_iri,
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
        return logical_source

    def __subject_map__(self, map_iri):
        subject_map = SimpleNamespace()
        subject_map_bnode = self.rml.value(
            subject=map_iri,
            predicate=NS_MGR.rr.subjectMap)
        if subject_map_bnode is None:
            return
        subject_map.class_ = self.rml.value(
            subject=subject_map_bnode,
            predicate=getattr(NS_MGR.rr,"class"))
        subject_map.template = self.rml.value(
            subject=subject_map_bnode,
            predicate=NS_MGR.rr.template)
        subject_map.termType = self.rml.value(
            subject=subject_map_bnode,
            predicate=NS_MGR.rr.termType)
        subject_map.deduplicate = self.rml.value(
            subject=subject_map_bnode,
            predicate=NS_MGR.kds.deduplicate)
        return subject_map

    def __predicate_object_map__(self, map_iri):
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
            pred_obj_maps.append(pred_obj_map)
        return pred_obj_maps

    def generate_term(self, **kwargs):
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
            
    def execute(self, triple_map, **kwargs):
        """Placeholder method should be overridden by child classes"""
        pass

    def run(self, **kwargs):
        """Run method iterates through triple maps and calls the execute
        method"""
        if not 'timestamp' in kwargs:
            kwargs['timestamp'] = datetime.datetime.utcnow().isoformat()
        for map_key, triple_map in self.triple_maps.items():
            if map_key not in self.parents:
                self.execute(triple_map, **kwargs) 

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
               
    def execute(self, triple_map, **kwargs):
        """Method executes mapping between source 

        Args:
            triple_map(SimpleNamespace): Triple Map
            
        """
        subjects = []
        for element in self.source.findall(
            str(triple_map.logicalSource.iterator),
            self.xml_ns):
            subject = self.generate_term(term_map=triple_map.subjectMap, 
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
                    for i, found_elem in enumerate(found_elements):
                        if found_elem.text is None or len(found_elem.text) < 1:
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
                        if triple_map.subjectMap.deduplicate == predicate:
                            existing_subject = self.__deduplicate__(triple_map.subjectMap,
                                subject,
                                ref_obj)
                            if existing_subject is not None:
                                subject = existing_subject
                        if subject is None:
                            print(predicate, ref_obj)
                        self.output.add((subject, 
                                         predicate, 
                                         ref_obj))
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
        super(XMLProcessor, self).run(**kwargs)


        
PREFIX = ""
for r in dir(NS_MGR):
    if r.startswith("__") or r is not None:
        continue
    PREFIX += "PREFIX {0}: <{1}>\n".format(r, getattr(NS_MGR, r))


GET_TRIPLE_MAPS = PREFIX + """
SELECT DISTINCT ?map
WHERE {
    ?map rdf:type rr:TriplesMap .
}"""
