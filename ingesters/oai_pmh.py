"""OAI-PMH to BIBFRAME 2.0 command-line ingester"""
__author__ = "Jeremy Nelson, Mike Stabile"

import click
import datetime
import logging
import xml.etree.ElementTree as etree
import rdflib
import requests
import urllib.parse

from .ingester import new_graph, NS_MGR
from .dc import DCIngester
from .mods import MODSIngester
from .rels_ext import RELSEXTIngester

NS = {"oai_pmh": "http://www.openarchives.org/OAI/2.0/"}

NS_MGR.bind('fedora', 'info:fedora/fedora-system:def/relations-external#')
NS_MGR.bind('fedora-model', 'info:fedora/fedora-system:def/model#')

class OAIPMHIngester(object):
    IDENT_XPATH = "oai_pmh:ListIdentifiers/oai_pmh:header/oai_pmh:identifier"
    MODS_XPATH = "oai_pmh:ListMetadataFormats/oai_pmh:metadataFormat[oai_pmh:metadataPrefix='mods']"
    TOKEN_XPATH = "oai_pmh:ListIdentifiers/oai_pmh:resumptionToken"

    def __init__(self, **kwargs):
        self.repository_url = kwargs.get("repository")
        self.oai_pmh_url = urllib.parse.urljoin(self.repository_url, "oai2")
        rules_ttl = kwargs.get("rules_ttl")
        self.identifiers = dict()
        self.metadataPrefix = "oai_dc"
        metadata_result = requests.get("{}?verb=ListMetadataFormats".format(
            self.oai_pmh_url))
        #ident_result = "oai_pmh:Identify/oai_pmh:description/oai_ident:oai-identifier/oai_ident:repositoryIdentifier"
        metadata_doc = etree.XML(metadata_result.text)
        # 
        if metadata_doc.find(OAIPMHIngester.MODS_XPATH, NS):
            self.metadata_ingester = MODSIngester(rules_ttl=rules_ttl)
            self.metadataPrefix = "mods"
        else:
            self.metadata_ingester = DCIngester(rules_ttl=rules_ttl)

    
    def harvest(self):
        """Method harvests all identifiers using ListIdentifiers"""
        initial_url = "{0}?verb=ListIdentifiers&metadataPrefix={1}".format(
            self.oai_pmh_url,
            self.metadataPrefix)
        initial_result = requests.get(initial_url)
        if initial_result.status_code > 399:
            raise ValueError("Cannot Harvest {}, result {}".format(
                self.oai_pmh_url,
                initial_result.text))
        initial_doc = etree.XML(initial_result.text)
        resume_token = initial_doc.find(OAIPMHIngester.TOKEN_XPATH, NS)
        for r in initial_doc.findall(OAIPMHIngester.IDENT_XPATH, NS):
            ident = r.text
            if not ident in self.identifiers:
                self.identifiers[ident] = 1
        total_size = int(resume_token.attrib.get("completeListSize", 0))
        start = datetime.datetime.utcnow()
        msg = "Started Retrieval of {} Identifiers {}".format(total_size, start)
        click.echo(msg)
        while len(self.identifiers) < total_size:
            continue_url = "{0}?verb=ListIdentifiers&resumptionToken={1}".format(
                self.oai_pmh_url,
                resume_token.text)
            result = requests.get(continue_url)
            shard_doc = etree.XML(result.text)
            resume_token = shard_doc.find(OAIPMHIngester.TOKEN_XPATH, NS)
            for r in shard_doc.findall(OAIPMHIngester.IDENT_XPATH, NS):
                if not r.text in self.identifiers:
                    self.identifiers[r.text] = 1
            click.echo(".", nl=False)
        end = datetime.datetime.utcnow()
        msg = "\nFinished at {}, total time {} minutes".format(
            end,
            (end-start).seconds / 60.0)
        print(msg)


class IslandoraIngester(OAIPMHIngester):
    """Islandora Ingester brings together multiple ingesters to deal with MODS and 
    RELS-EXT Metadata in order to generate BIBFRAME RDF"""

    def __init__(self, **kwargs):
        super(IslandoraIngester, self).__init__(**kwargs)
        self.repo_graph = new_graph()

    def harvest(self, **kwargs):
        """Overloaded harvest method takes optional RELS-EXT ttl file"""
        start = datetime.datetime.utcnow()
        msg = "Starting OAI-PMH harvest of PIDS from Islandora at {}".format(
            start)
        click.echo(msg)
        super(IslandoraIngester, self).harvest()
        for i,row in enumerate(self.identifiers.keys()):
            if not i%10 and i > 0:
                click.echo(".", nl=False)
            if not i%100:
                click.echo(i, nl=False)
            pid = row.split(":")[-1].replace("_", ":")
            item_url = urllib.parse.urljoin(self.repository_url,
                "islandora/object/{0}/".format(pid))
            item_uri = rdflib.URIRef(item_url)
            rels_ext_url = urllib.parse.urljoin(item_url,
                "datastream/RELS-EXT")
            rels_ext_result = requests.get(rels_ext_url)
            if rels_ext_result.status_code > 399:
                error = "{} RELS-EXT not found".format(pid)
                click.echo(error, nl=False)
                continue
            rels_ext = RELSEXTIngester(
                rules_ttl=kwargs.get('rules_rels_ext'),
                source=rels_ext_result.text)
            # Skips if object is part of a Compound Object
            try:
                next(rels_ext.source.objects(
                    predicate=NS_MGR.fedora.isConstituentOf))
                continue
            except StopIteration:
                pass
            mods_url = urllib.parse.urljoin(item_url,
                "datastream/MODS")
            mods_result = requests.get(mods_url)
            try:
                self.metadata_ingester.transform(
                    item_uri=item_uri,
                    xml=mods_result.text)
            except:
                logging.error("{} Error with {}".format(
                    sys.exc_info()[-1],
                    item_uri))
                continue
            instance_uri = self.metadata_ingester.graph.value(
                subject=item_uri,
                predicate=NS_MGR.bf.itemOf)
            rels_ext.transform(instance_uri=instance_uri,
                item_uri=item_uri)
            self.metadata_ingester.graph += rels_ext.graph
            if 'out_file' in kwargs:
                self.repo_graph += self.metadata_ingester.graph
            else:
                self.metadata_ingester.add_to_triplestore()
        if 'out_file' in kwargs:
            with open(kwargs.get('out_file'), 'wb+') as fo:
                fo.write(self.repo_graph.serialize(format='turtle'))
        end = datetime.datetime.utcnow()
        msg = "\nIslandora OAI-PMH harvested at {}, total time {} mins".format(
            end,
            (end-start).seconds / 60.0)
        click.echo(msg)
