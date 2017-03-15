"""mapping.py - RDF Mapping Language Base Class contains TriplesMaps to
compare with mapping of source data to output RDF"""
__author__ = "Jeremy Nelson, Mike Stabile"

try:
    from lxml import etree
except ImportError:
    import xml.etree.ElementTree as etree

import rdflib
from .models import TripleMap, LogicalSource, SubjectMap

def generate_pred_obj_map(rml_graph, pred_obj_bnode):
    predicate_constant = rml_graph.value(subject=pred_obj_bnode,
        predicate=RR.predicate)
    obj_constant = rml_graph.value(subject=pred_obj_bnode,
            predicate=getattr(RR, "object"))
    new_pred_obj_map = PredicateObjectMap()
    if predicate_constant is not None:
        new_pred_obj_map.predicate_maps.append(
            ConstantMap(predicate_constant))
    if obj_constant is not None:
        new_pred_obj_map.object_maps.append(
            ConstantMap(obj_constant))
    pred_map_bnode = rml_graph.value(subject=pred_obj_bnode,
        predicate=RR.predicateMap)
    if pred_map_bnode is not None:
        reference = rml_graph.value(subject=pred_map_bnode,
            predicate=RR.reference)
        if reference is not None:
            new_pred_obj_map.predicate_maps.append(
                ReferenceMap(reference))
    obj_map_bnode = rml_graph.value(subject=pred_obj_bnode,
        predicate=RR.objectMap)
    if obj_map_bnode is not None:
        reference = rml_graph.value(subject=obj_map_bnode,
            predicate=RR.reference)
        if reference is not None:
            new_pred_obj_map.object_maps.append(
                ReferenceMap(reference))
    return new_pred_obj_map    

        
 


def generate_triples_map(rml_graph, map_iri):
    """Function takes a rml_graph and a map_iri and returns a TripleMap
    instance.

    Args:
        rml_graph(rdflib.Graph): RDF Mapping Graph
        map_iri(rdflib.URIRef): TripleMap IRI

    Returns:
        TripleMap        
    """
    logical_source_bnode = rml_graph.value(subject=map_iri,
                                           predicate=RML.logicalSource)
    subject_map_bnode = rml_graph.value(subject=map_iri,
                                        predicate=RR.subjectMap)
    pred_obj_maps = []
    for pred_obj_bnode in rml_graph.objects(subject=map_iri,
                                           predicate=RR.predicateOrObjectMap):
        pred_obj_maps.append(generate_pred_obj_map(rml_graph, pred_obj_bnode))
    return TripleMap(
        LogicalSource(rml_graph.value(subject=logical_source_bnode,
                                      predicate=RML.source),
                      rml_graph.value(subject=logical_source_bnode,
                                      predicate=RML.iterator)),
        SubjectMap(template=rml_graph.value(subject=subject_map_bnode,
                                            predicate=RR.template),
                   class_=rml_graph.value(subject=subject_map_bnode,
                                          predicate=getattr(RR, 'class')),
                   constant=rml_graph.value(subject=subject_map_bnode,
                                            predicate=RR.constant)),
        pred_obj_maps)

class RMLMapping(object):

    def __init__(self, **kwargs):
        """Creates an instance of the RMLMapping Class

        kwargs:
            rml_source(str):  Full Path to RML RDF turtle file
        """
        rml_source = kwargs.get('rml_source')
        if rml_source is None:
            raise ValueError("RDF Mapping Source required")
        self.base_url = kwargs.get('base_url', 'http://bibcat.org/')
        self.rml = rdflib.Graph()
        self.rml.parse(rml_source, format='turtle')
        self.triples_maps = []
        self.output = rdflib.Graph()
        for row in self.rml.query("""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rr: <http://www.w3.org/ns/r2rml#>

        SELECT DISTINCT ?map
        WHERE {
                ?map rdf:type rr:TriplesMap
        }"""):
            self.triples_maps.append(generate_triples_map(self.rml, row[0]))
        


    def process(self, **kwargs):
        """Should be overridden by child classes"""
        pass


class XMLMap(RMLMapping):
    """Base XML Map for processing source XML files into RDF"""

    def __init__(self, **kwargs):
        super(XMLMap, self).__init__(**kwargs)


    def process(self, xml):
        """Initializes an instance of XMLMap class

        Args:
            xml(str or etree.ElementTree): ElementTree or raw XML string
        """
        if not (isinstance(xml, etree.ElementTree) or\
                isinstance(xml, etree.Element)):
            xml = etree.XML(xml)
        self.source = xml
        
        
        
