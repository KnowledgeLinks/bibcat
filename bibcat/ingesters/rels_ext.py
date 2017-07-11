"""Fedora 3.x RELS-EXTseries to BIBFRAME 2.0 ingester

This ingester is not intended to generated fully formed BF RDF but 
supplement existing ingesters like MODS and DC. The RELS-EXT ingester adds
additional properties and classes to existing BF entities. 

"""
__author__ = "Jeremy Nelson, Mike Stabile"

import os
import rdflib
import requests

from bibcat.rml.processor import XMLProcessor

class RELSEXTIngester(XMLProcessor):

    def __init__(self, **kwargs):
        rules = ["bibcat-rels-ext.ttl"]
        if "rules_ttl" in kwargs:
            tmp_rules = kwargs.get("rules_ttl")
            if isinstance(tmp_rules, str):
                rules.append(tmp_rules)
            elif isinstance(tmp_rules, list):
                rules.extend(tmp_rules)
        super(RELSEXTIngester, self).__init__(
            rml_rules=rules,
            base_url=kwargs.get("base_url", "http://bibcat.org/"),
            institution_iri=kwargs.get("institution_iri"),
            namespaces={'fedora': 'info:fedora/fedora-system:def/relations-external#',
                'fedora-model': 'info:fedora/fedora-system:def/model#',
                'islandora': 'http://islandora.ca/ontology/relsext#',
                'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'})
