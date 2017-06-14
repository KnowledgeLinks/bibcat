"""OAI-PMH to BIBFRAME 2.0 ingester Classes"""
__author__ = "Jeremy Nelson, Mike Stabile"

import click
import datetime
import io
import logging
import os
try:
    from lxml import etree
except ImportError:
    import xml.etree.ElementTree as etree
import rdflib
import requests
import sys
import urllib.parse
import uuid

from .ingester import new_graph, NS_MGR, BIBCAT_BASE
from .rels_ext import RELSEXTIngester
from ..rml.processor import XMLProcessor

NS = {"oai_pmh": "http://www.openarchives.org/OAI/2.0/"}

NS_MGR.bind('fedora', 'info:fedora/fedora-system:def/relations-external#')
NS_MGR.bind('fedora-model', 'info:fedora/fedora-system:def/model#')

class OAIPMHIngester(object):
    IDENT_XPATH = "oai_pmh:ListIdentifiers/oai_pmh:header/oai_pmh:identifier"
    TOKEN_XPATH = "oai_pmh:ListIdentifiers/oai_pmh:resumptionToken"

    def __init__(self, **kwargs):
        self.repository_url = kwargs.get("repository")
        if self.repository_url is None:
            raise ValueError("repository_url must have a value")
        self.oai_pmh_url = urllib.parse.urljoin(self.repository_url, "oai2")

        self.identifiers = dict()
        self.metadataPrefix = "oai_dc"
        metadata_result = requests.get("{}?verb=ListMetadataFormats".format(
            self.oai_pmh_url))
        metadata_formats = metadata_result.text
        if isinstance(metadata_result.text, str):
            metadata_formats = metadata_result.text.encode()
        self.metadata_formats_doc = etree.XML(metadata_formats)
        self.metadata_ingester = None
    
    def harvest(self, sample_size=None):
        """Method harvests all identifiers using ListIdentifiers"""
        initial_url = "{0}?verb=ListIdentifiers&metadataPrefix={1}".format(
            self.oai_pmh_url,
            self.metadataPrefix)
        initial_result = requests.get(initial_url)
        if initial_result.status_code > 399:
            raise ValueError("Cannot Harvest {}, result {}".format(
                self.oai_pmh_url,
                initial_result.text))
        raw_initial = initial_result.text
        if isinstance(raw_initial, str):
            raw_initial = raw_initial.encode()
        initial_doc = etree.XML(raw_initial)
        resume_token = initial_doc.find(OAIPMHIngester.TOKEN_XPATH, NS)
        for r in initial_doc.findall(OAIPMHIngester.IDENT_XPATH, NS):
            ident = r.text
            if not ident in self.identifiers:
                self.identifiers[ident] = 1
        total_size = int(resume_token.attrib.get("completeListSize", 0))
        
        start = datetime.datetime.utcnow()
        msg = "Started Retrieval of {} Identifiers {}".format(total_size, start)
        try:
            click.echo(msg)
        except io.UnsupportedOperation:
            print(msg)
        while len(self.identifiers) < total_size:
            continue_url = "{0}?verb=ListIdentifiers&resumptionToken={1}".format(
                self.oai_pmh_url,
                resume_token.text)
            result = requests.get(continue_url)
            shard_raw = result.text
            if isinstance(shard_raw, str):
                shard_raw = shard_raw.encode()
            shard_doc = etree.XML(shard_raw)
            resume_token = shard_doc.find(OAIPMHIngester.TOKEN_XPATH, NS)
            for r in shard_doc.findall(OAIPMHIngester.IDENT_XPATH, NS):
                if not r.text in self.identifiers:
                    self.identifiers[r.text] = 1
            try:
                click.echo(".", nl=False)
            except io.UnsupportedOperation:
                print(".", end="")
        # Creates a random sample of identifiers of sample_size length
        if sample_size is not None:
            import random
            rand_keys = []
            for i in range(int(sample_size)):
                rand_keys.append(random.randint(0, total_size))
            for i, key in enumerate(list(self.identifiers.keys())):
                if not i in rand_keys:
                    self.identifiers.pop(key)
        msg = "Sample size {} identifiers size {}".format(sample_size, len(self.identifiers))
        try:
            click.echo(msg)
        except io.UnsupportedOperation:
            print(msg)        
        end = datetime.datetime.utcnow()
        msg = "\nFinished at {}, total time {} minutes".format(
            end,
            (end-start).seconds / 60.0)
        try:
            click.echo(msg)
        except io.UnsupportedOperation:
            print(msg)


class ContentDMIngester(OAIPMHIngester):
    """ContentDM Ingester provides an interface to OCLC's ContentDM&copy; 
    repository"""

    def __init__(self, **kwargs):
        super(ContentDMIngester, self).__init__(**kwargs) 

    def __process_dc__(self, **kwargs):
        """Method processes Dublin Core RDF"""

    def harvest(self, **kwargs):
        """Method harvests either the entire repository contents or selected
        collections"""
        start = datetime.datetime.utcnow()
        msg = "Starting OAI-PMH harvest of PIDS from Islandora at {}".format(
            start)
        try:
            click.echo(msg)
        except io.UnsupportedOperation:
            print(msg)



class IslandoraIngester(OAIPMHIngester):
    """Islandora Ingester brings together multiple ingesters to deal with MODS and 
    RELS-EXT Metadata in order to generate BIBFRAME RDF"""
    MODS_XPATH = "oai_pmh:ListMetadataFormats/oai_pmh:metadataFormat[oai_pmh:metadataPrefix='mods']"

    def __init__(self, **kwargs):
        super(IslandoraIngester, self).__init__(**kwargs)
        self.repo_graph = new_graph()
        self.base_url = kwargs.get('base_url')
        rules_ttl = kwargs.get("rules_ttl", [])
        if self.metadata_formats_doc.find(
            IslandoraIngester.MODS_XPATH, 
            NS) is not None:
            self.metadataPrefix = "mods"
            for rule_name in ["rml-bibcat-base.ttl", 
                              "rml-bibcat-mods-to-bf.ttl"]:
                rules_ttl.append(os.path.join(BIBCAT_BASE,
                    os.path.join("rdfw-definitions", rule_name)))
            self.metadata_ingester = XMLProcessor(
                rml_rules=rules_ttl,
                base_url=self.base_url,
                triplestore_url=kwargs.get("triplestore_url"),
                institution_iri=kwargs.get("institution_iri"),
                namespaces={self.metadataPrefix: str(NS_MGR.mods)})
        else:
            rules_ttl.append(
                os.path.join(BIBCAT_BASE,
                    os.path.join("rdfw-definitions", "rml-bibcat-base.ttl")))
            self.metadata_ingester = XMLProcessor(
                rml_rules=rules_ttl)


    def __process_mods__(self, **kwargs):
        """Extracts MODS datastream from the item_url

        keyword args:
            item_url(str): URL For Fedora URL
        """
        item_url = kwargs.get('item_url')
        mods_url = urllib.parse.urljoin(item_url,
            "datastream/MODS")
        mods_result = requests.get(mods_url)
        base_url = kwargs.get("base_url")
        if base_url is None and "base_url" in self.metadata_ingester.constants:
            base_url = self.metadata_ingester.constants.get("base_url")
        else:
            raise ValueError("base_url required for __process_mods__")
        instance_url = kwargs.get("instance_url")
        if instance_url is None:
            instance_url = "{0}/{1}".format(base_url, uuid.uuid1()) 
        try:
            self.metadata_ingester.run(mods_result.text,
                base_url=base_url,
                id=uuid.uuid1,
                item_iri=item_url,
                instance_iri=instance_url)
        except:
            logging.error("{} Error with {}".format(
                sys.exc_info()[1],
                item_url))

    def __process_rels_ext__(self, **kwargs):
        """Extracts RELS-EXT and returns RELS-EXT ingester"""
        item_url = kwargs.get('item_url')
        rels_ext_url = urllib.parse.urljoin(item_url,
            "datastream/RELS-EXT")
        rels_ext_result = requests.get(rels_ext_url)
        if rels_ext_result.status_code > 399:
            error = "{} RELS-EXT not found".format(item_url)
            try:
                 click.echo(error, nl=False)
            except io.UnsupportedOperation:
                 print(error, end=" ")
            return None, None
        base_url = kwargs.get("base_url")
        if base_url is None and self.base_url is not None:
            base_url = base_url
        else:
            raise ValueError("base_url required for __process_rels_ext__") 
        rels_ext = RELSEXTIngester(base_url=base_url)
        rels_ext_doc = etree.XML(rels_ext_result.text)
        # Returns None if object is part of a Compound Object
        if rels_ext_doc.find("rdf:Description/fedora:isConstituentOf",
            rels_ext.xml_ns) is not None:
            return None, None
        return rels_ext, rels_ext_doc


    def harvest(self, **kwargs):
        """Overloaded harvest method takes optional RELS-EXT ttl file"""
        start = datetime.datetime.utcnow()
        msg = "Starting OAI-PMH harvest of PIDS from Islandora at {}".format(
            start)
        try:
            click.echo(msg)
        except io.UnsupportedOperation:
            print(msg)
        super(IslandoraIngester, self).harvest(
            sample_size=kwargs.get('sample_size'))
        for i,row in enumerate(self.identifiers.keys()):
            if not i%10 and i > 0:
                try:
                    click.echo(".", nl=False)
                except io.UnsupportedOperation:
                    print(".", end="")
            if not i%100:
                try:
                    click.echo(i, nl=False)
                except io.UnsupportedOperation:
                    print(i, end="")
            pid = row.split(":")[-1].replace("_", ":")
            item_url = urllib.parse.urljoin(self.repository_url,
                "islandora/object/{0}/".format(pid))
            item_uri = rdflib.URIRef(item_url)
            rels_ext, rels_ext_doc = self.__process_rels_ext__(
                item_url=item_url)
            if rels_ext is None:
                continue
            self.__process_mods__(item_url=item_url)
            instance_uri = self.metadata_ingester.output.value(
                subject=item_uri,
                predicate=NS_MGR.bf.itemOf)
            rels_ext.run(rels_ext_doc,
                instance_iri=instance_uri)
            self.metadata_ingester.output += rels_ext.output
            if 'out_file' in kwargs:
                self.repo_graph += self.metadata_ingester.output
            else:
                self.metadata_ingester.add_to_triplestore()
        if 'out_file' in kwargs:
            with open(kwargs.get('out_file'), 'wb+') as fo:
                fo.write(self.repo_graph.serialize(format='turtle'))
        end = datetime.datetime.utcnow()
        msg = "\nIslandora OAI-PMH harvested at {}, total time {} mins".format(
            end,
            (end-start).seconds / 60.0)
        try:
            click.echo(msg)
        except io.UnsupportedOperation:
            print(msg)
