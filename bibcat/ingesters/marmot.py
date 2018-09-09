"""Custom ingester for the Marmot Consortium custom JSON feed for DP.LA
harvesting"""
__author__ = "Jeremy Nelson"

import rdflib

from .ingester import Ingester

class MarmotIngester(Ingester):

    def __init__(self, **kwargs):
        rml_rules = ['bibcat-base.ttl']
        rml_rules.extend(kwargs.get("rules", []))
        super(MarmotIngester, self).__init__(**kwargs)
        self.marmot_members = kwargs.get("members", dict())
        
    def __load_members__(self, marmot_org_ttl):
        marmot_orgs = rdflib.Graph()
        marmot_orgs.parse(marmot_org_ttl, format='turtle')
        for library_iri in marmot_orgs.subjects(predicate=rdflib.RDF.type,
            object=SCHEMA.Library):
            label = marmot_orgs.value(subject=library_iri, predicate=rdflib.RDFS.label)
            self.marmot_members[str(label)] = library_iri
        for library_iri in marmot_orgs.subjects(predicate=rdflib.RDF.type,
            object=SCHEMA.Library):
            label = marmot_orgs.value(subject=library_iri, predicate=rdflib.RDFS.label)
            self.marmot_members[str(label)] = library_iri


