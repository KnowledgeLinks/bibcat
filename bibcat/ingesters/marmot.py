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
        marmot_ttl = kwargs.get('marmot-ttl')
        self.marmot_members = dict()
        if marmot_ttl is not None:
            self.__load_members__(marmot_ttl)
        
        
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

    def load_feed_url(self, url):
        result = requests.get(url)
        if result.status_code < 400:
            marmot_json = result.json()
        else:
            error_msg = "{} Error getting {}, sleeping 10 seconds".format(
                result.text,
                url)
            try:
                click.echo(error_msg)
            except:
                print(error_msg)
            time.sleep(10)
            result = requests.get(url)
            marmot_json = result.json()
        docs = marmot_json['result']['docs']
        total_pages = marmot_json['result']['numPages']
        return docs, total_pages

   



