"""models.py - RML Models defines TripleMaps and constituent classes as 
described at <http://rml.io/spec.html>"""
__author__ = "Jeremy Nelson, Mike Stabile"

import rdflib

class TripleMap(object):
    """Class for <https://www.w3.org/ns/r2rml#TriplesMap>"""

    def __init__(self, 
        logical_source, 
        subject_map, 
        predicate_object_maps=[]):
        if not isinstance(logical_source, LogicalSource):
            raise ValueError(
                "{} not a LogicalSource instance".format(logical_source))
        self.logical_source = logical_source
        if not isinstance(subject_map, SubjectMap):
            raise ValueError("{} not a SubjectMap instance".format(
                subject_map))
        self.subject_map = subject_map
        self.predicate_object_maps = []
        for row in predicate_object_maps:
            if not isinstance(row, PredicateObjectMap):
                raise ValueError("{} not a PredicateObjectMap".format(
                    row))
            self.predicate_object_maps.append(row)



class LogicalSource(object):
    """Class for <http://semweb.datasciencelab.be/ns/rml#LogicalSource>"""

    def __init__(self, source, iterator, reference_formulations=[]):
        self.source = source
        self.iterator = iterator
        self.reference_formulations = reference_formulations


class TermMap(object):
    """Generates an RDF Term from a logical reference"""

    def __init__(self, references=[]):
        self.references = references
        self.term = None 

class ConstantMap(TermMap):

    def __init__(self, constant):
        super(ConstantRDF, self).__init__(references=[])
        self.term = constant

class ReferenceMap(TermMap):

    def __init__(self, reference):
        super(ReferenceMap, self).__init__(references=[reference,])

class TemplateMap(TermMap):

    def __init__(self, template):
        super(TemplateMap, self).__init__()
        self.template = template
        

class SubjectMap(ConstantMap, ReferenceMap, TemplateMap):
    """Class for <http://www.w3.org/ns/r2rml#SubjectMap>"""

    def __init__(self, 
        template=None, 
        class_=None,
        constant=None):
        if constant is not None: 
            if isinstance(constant, rdflib.URIRef):
                super(ConstantMap, self).__init__(constant)
            else:
                raise ValueError("SubjectMap constant must be an IRI")
        if template is not None:
            super(TemplateMap, self).__init__(template)
        self.rdfs_class = class_
        
        
        
                     
