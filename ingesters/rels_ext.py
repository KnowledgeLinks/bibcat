"""Fedora 3.x RELS-EXTseries to BIBFRAME 2.0 ingester

This ingester is not intended to generated fully formed BF RDF but 
supplement existing ingesters like MODS and DC. The RELS-EXT ingester adds
additional properties and classes to existing BF entities. 

"""
__author__ = "Jeremy Nelson, Mike Stabile"

import rdflib
import requests


from .ingester import Ingester, NS_MGR



class RELSEXTIngester(Ingester):

    def __init__(self, **kwargs):
        rules = ['kds-bibcat-rels-ext.ttl']
        if "rules_ttl" in kwargs:
            tmp_rules = kwargs.get("rules_ttl")
            if isinstance(tmp_rules, str):
                rules.append(tmp_rules)
            elif isinstance(tmp_rules, list):
                rules.extend(tmp_rules)
        if 'source' in kwargs:
            if isinstance(kwargs.get('source'), str):
                source = rdflib.ConjunctiveGraph()
                source.parse(data=kwargs.get('source'))
                kwargs['source'] = source
        kwargs['rules_ttl'] = rules        
        super(RELSEXTIngester, self).__init__(**kwargs)

    
    def __handle_linked_pattern__(self, **kwargs):
        entity = kwargs.get("entity")
        destination_class = kwargs.get("destination_class")
        destination_property = kwargs.get("destination_property")
        target_property = kwargs.get("target_property")
        rule = kwargs.get("rule")
        if isinstance(rule, rdflib.BNode):
            for pred, obj in self.rules_graph.predicate_objects(subject=rule):
                if self.source.value(predicate=pred, object=obj) is not None:
                    self.graph.add((entity, 
                                    destination_property, 
                                    destination_class))

    def transform(self, xml=None, instance_uri=None, item_uri=None):
        """Overrides parent class transform and adds XML-specific
        transformations

        Args:
            xml(str): XML or None
            instance_uri: URIRef for instance or None
            item_uri: URIREf for item or None
        """
        if xml is not None:
            if isinstance(xml, str):
                source = rdflib.ConjunctiveGraph()
                source.parse(data=xml)
                self.source = source
        self.update_linked_classes(NS_MGR.bf.Instance, instance_uri)
        self.update_linked_classes(NS_MGR.bf.Item, item_uri)


                



