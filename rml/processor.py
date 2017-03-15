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
        self.output = rdflib.Graph()
        self.source = None

    def __logical_source__(self, map_iri):
        logical_src_bnode = self.rml.value(subject=map_iri,
            predicate=NS_MGR.rml.logicalSource)


    def execute(self, triple_map):
        pass

    def run(self, **kwargs):
        for row in self.rml.query(GET_TRIPLE_MAPS):
            triple_map_iri = row[0]
            self.__logical_source__(triple_map_iri)
            self.execute() 
        
        
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
