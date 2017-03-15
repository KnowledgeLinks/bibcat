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

    def generate(self):
        return self.term

class ConstantMap(TermMap):

    def __init__(self, constant):
        super(ConstantMap, self).__init__(references=[])
        self.term = constant


class PredicateMap(TermMap):

    def __init__(self, predicate):
        super(PredicateMap, self).__init__(references=[])
        if not isinstance(predicate, rdflib.BNode):
            raise ValueError("PredicateMap cannot be IRI")            
            

class ReferenceMap(TermMap):

    def __init__(self, reference):
        super(ReferenceMap, self).__init__(references=[reference,])

    def generate(self, **kwargs):
        


class TemplateMap(TermMap):
    var_regex = re.compile(r"{(\w+)}")

    def __init__(self, **kwargs):
        super(TemplateMap, self).__init__()
        self.template = kwargs.get("template")
        self.variables = TemplateMap.var_regex.findall(self.template)
        for var in self.variables:
            if var in kwargs:
                setattr(self, var, kwargs.get(var))

    def generate(self, **kwargs):
        template_vars = dict()
        for var in self.variables:
            if hasattr(self, var):
                value = getattr(self, var)
            elif var in kwargs:
                value = kwargs.get(var)
            else:
                raise ValueError("variable {} required".format(var))
            template_vars[var] = value
        self.term = rdflib.URIRef(self.template.format(**kwargs))
        return super(TemplateMap, self).generate()
        
        
class BaseTripleMap(ConstantMap, ReferenceMap, TemplateMap):

    def  __init__(self, **kwargs):
        template=kwargs.get("template")
        constant=kwargs.get("constant")
        if template is not None and constant is not None:
            raise ValueError("Cannot have both template and constant")
        if template is not None:
            TemplateMap.__init__(self, template)
        if constant is not None:
            ConstantMap.__init__(self, constant)       


class ObjectMap(BaseTripleMap):

    def __init__(self, 

class SubjectMap(BaseTripleMap):
    """Class for <http://www.w3.org/ns/r2rml#SubjectMap>"""

    def __init__(self, **kwargs):
        constant = kwargs.get("constant")
        if constant is not None and not isinstance(constant, rdflib.URIRef):
            raise ValueError("SubjectMap constant must be an IRI")
        super(BaseTripleMap, self).__init__(**kwargs)
        self.class_ = kwargs.get("class")

    def generate(self):
        term = super(SubjectMap, self).generate()
        if term is None and hasattr(self, "template"):
            raw_template = str(self.template)
            
            

    

class PredicateObjectMap(object):

    def __init__(self, predicate_maps, object_maps):
        self.predicate_maps = predicate_maps
        self.object_maps = object_maps
        
