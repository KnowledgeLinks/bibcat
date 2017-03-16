__author__ = "Jeremy Nelson"

import rdflib
from types import SimpleNamespace

NS_MGR = SimpleNamespace()
setattr(NS_MGR, "rdf", rdflib.RDF)
setattr(NS_MGR, "rdfs", rdflib.RDFS)
setattr(NS_MGR, "rml", rdflib.Namespace("http://semweb.mmlab.be/ns/rml#"))
setattr(NS_MGR, "rr", rdflib.Namespace("http://www.w3.org/ns/r2rml#"))


class Processor(object):

    def __init__(self, rml_rules):
        self.rml = rdflib.Graph()
        self.rml.parse(rml_rules, format='turtle')
        self.source = None
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
            pred_obj_map.parentTriplesMap = self.rml.value(
                subject=obj_map_bnode,
                predicate=NS_MGR.rr.parentTriplesMap)
            pred_obj_map.reference = self.rml.value(
                subject=obj_map_bnode,
                predicate=NS_MGR.rr.reference)
            pred_obj_map.datatype = self.rml.value(
                subject=obj_map_bnode,
                predicate=NS_MGR.rr.datetype)
            pred_obj_maps.append(pred_obj_map)
        return pred_obj_maps

    def generate_term(self, **kwargs):
        term_map = kwargs.pop('map')
        if term_map.termType == NS_MGR.rr.BlankNode:
            return rdflib.BNode()
        if term_map.template is not None:
            return rdflib.URIRef(
                    term_map.template.format(**kwargs))
        


    def execute(self, triple_map):
        pass

    def run(self):
        output = rdflib.Graph()
        for map_key, triple_map in self.triple_maps.items():
            output += self.execute(triple_map) 
        return output

class XMLProcessor(Processor):
    """XML RDF Mapping Processor"""

    def __init__(self, **kwargs):
        rml_rules = kwargs.get("rml_rules")
        super(XMLProcessor, self).__init__(rml_rules)
        self.xml_ns = kwargs.get("namespaces", {})
       
    def execute(self, triple_map):
        for element in self.source.find_all(
            str(triple_map.logicalSource.iterator),
            self.xml_ns):
            for row in triple_map.predicateObjectMap:
                if row.parentTriplesMap is not None:
                    return self.existing_maps[triple_maps.parentTriplesMap]
                if row.reference is not None:
                    


    def run(self, xml):
        if isinstance(xml, str):
            self.source = etree.XML(xml)
        output = super(XMLProcessor, self).run()
        return output


        
PREFIX = ""
for r in dir(NS_MGR):
    if r.startswith("__"):
        continue
    PREFIX += "PREFIX {0}: <{1}>\n".format(r, getattr(NS_MGR, r))
GET_TRIPLE_MAPS = PREFIX + """
SELECT DISTINCT ?map
WHERE {
    ?map rdf:type rr:TriplesMap .
}"""    
