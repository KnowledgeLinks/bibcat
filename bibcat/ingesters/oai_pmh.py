"""OAI-PMH to BIBFRAME 2.0 ingester Classes"""
__author__ = "Jeremy Nelson, Mike Stabile"

import click
import datetime
import io
import logging
import os
import time
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
from rdfframework.connections import ConnManager
from rdfframework.rml.processor import XMLProcessor

NS = {"oai_pmh": "http://www.openarchives.org/OAI/2.0/",
      'dc': 'http://purl.org/dc/elements/1.1/', 
      'oai_dc': 'http://www.openarchives.org/OAI/2.0/oai_dc/'}
try:
    NS_MGR.bind('fedora', 'info:fedora/fedora-system:def/relations-external#')
    NS_MGR.bind('fedora-model', 'info:fedora/fedora-system:def/model#')
except AttributeError:
    setattr(NS_MGR, 'fedora', 'info:fedora/fedora-system:def/relations-external#')
    setattr(NS_MGR, 'fedora-model', 'info:fedora/fedora-system:def/model#')

class OAIPMHIngester(object):
    IDENT_XPATH = "oai_pmh:ListIdentifiers/oai_pmh:header/oai_pmh:identifier"
    TOKEN_XPATH = "oai_pmh:ListIdentifiers/oai_pmh:resumptionToken"

    def __init__(self, **kwargs):
        self.oai_pmh_url = kwargs.get("repository")
        if self.oai_pmh_url is None:
            raise ValueError("repository must have a value")
        self.identifiers = dict()
        self.metadataPrefix = "oai_dc"
        metadata_url = "{}?verb=ListMetadataFormats".format(self.oai_pmh_url)
        metadata_result = requests.get(metadata_url)
        metadata_formats = metadata_result.text
        if isinstance(metadata_result.text, str):
            metadata_formats = metadata_result.text.encode()
        self.metadata_formats_doc = etree.XML(metadata_formats)
        self.processor = None
        self.repo_graph = None

    def __init_doc__(self, **kwargs):
        params = {"verb": "ListRecords",
                  "metadataPrefix": self.metadataPrefix}
        if "setSpec" in kwargs:
            params["set"] = kwargs.get("setSpec")
        initial_result = requests.get("{0}?{1}".format(
                self.oai_pmh_url,
                urllib.parse.urlencode(params)))
        initial_doc = etree.XML(initial_result.text.encode())
        token = initial_doc.find("oai_pmh:ListRecords/oai_pmh:resumptionToken", NS)
        records = initial_doc.findall("oai_pmh:ListRecords/oai_pmh:record", NS)
        count = 0
        deduplicator = kwargs.get("dedup")
        for i,rec in enumerate(records):
            count += 1
            self.processor.run(rec, **kwargs)
            if deduplicator is not None:
                deduplicator.run(self.processor.output)
            if self.repo_graph is None:
                self.repo_graph = self.processor.output
            else:
                self.repo_graph += self.processor.output
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
        return count, token
 
    
    def harvest(self, **kwargs):
        """Method harvests all identifiers using ListIdentifiers"""
        params = {"verb": "ListIdentifiers",
                  "metadataPrefix": self.metadataPrefix}
        if "setSpec" in kwargs:
            params["set"] = kwargs.get("setSpec")
        initial_url = "{0}?{1}".format(
            self.oai_pmh_url,
            urllib.parse.urlencode(params))
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
        if resume_token is not None:
            total_size = int(resume_token.attrib.get("completeListSize", 0))
        else:
            total_size = 0
        sample_size = kwargs.get('sample_size')
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
        self.triplestore_url = kwargs.get("triplestore_url")
        rml_rules = kwargs.get("rml_rules", [])
        if not isinstance(rml_rules, list):
            rml_rules = [rml_rules,]
        # Add rml base and OAI-PMH DC rules
        for rulefile in ["bibcat-oai-pmh-dc-xml-to-bf.ttl",
                         "bibcat-base.ttl"]:
            rml_rules.append(rulefile)
        self.processor = XMLProcessor(
            institution_iri=kwargs.get("institution_iri"),
            instance_iri = kwargs.get('instance_iri'),
            rml_rules=rml_rules,
            namespaces=NS)

    def __process_dc__(self, **kwargs):
        """Method processes Dublin Core RDF"""

    def harvest(self, **kwargs):
        """Method harvests either the entire repository contents or selected
        collections"""
        start = datetime.datetime.utcnow()
        msg = "Starting OAI-PMH harvest of PIDS from ContentDM at {}".format(
            start)
        try:
            click.echo(msg)
        except io.UnsupportedOperation:
            print(msg)
        count, token = self.__init_doc__(**kwargs)
        while token is not None:
            params = { "resumptionToken": token.text,
                       "verb": "ListRecords"}
            continue_url = "{0}?{1}".format(
                self.oai_pmh_url,
                urllib.parse.urlencode(params))
            shard_result = requests.get(continue_url)
            shard_doc = etree.XML(shard_result.text.encode())
            token = shard_doc.find("oai_pmh:ListRecords/oai_pmh:resumptionToken", NS)
            records = shard_doc.findall("oai_pmh:ListRecords/oai_pmh:record", NS)
            for rec in records:
                self.processor.run(rec, **kwargs)
                self.repo_graph += self.processor.output
                if not count%10 and count > 0:
                    try:
                        click.echo(".", nl=False)
                    except io.UnsupportedOperation:
                         print(".", end="")
                if not count%100:
                    try:
                        click.echo(count, nl=False)
                    except io.UnsupportedOperation:
                         print(count, end="")
                count += 1
                end = datetime.datetime.utcnow()
            if count > 8000:
                print(token.text, count)
        msg = "\nContentDM OAI-PMH harvested at {}, total time {} mins".format(
            end,
            (end-start).seconds / 60.0)
        try:
            click.echo(msg)
        except io.UnsupportedOperation:
            print(msg)       
        if 'out_file' in kwargs:
            self.repo_graph += self.processor.output
        else:
            self.add_to_triplestore()



class IslandoraIngester(OAIPMHIngester):
    """Islandora Ingester brings together multiple ingesters to deal with MODS and 
    RELS-EXT Metadata in order to generate BIBFRAME RDF"""
    MODS_XPATH = "oai_pmh:ListMetadataFormats/oai_pmh:metadataFormat[oai_pmh:metadataPrefix='mods']"

    def __init__(self, **kwargs):
        if not kwargs['repository'].endswith("oai2"):
            kwargs['repository'] = urllib.parse.urljoin(
                kwargs['repository'], 
                "oai2")
        self.repository = kwargs.get('repository')
        super(IslandoraIngester, self).__init__(**kwargs)
        self.repo_graph = rdflib.Graph()
        self.repo_graph.namespace_manager.bind("bf", "http://id.loc.gov/ontologies/bibframe/")
        self.repo_graph.namespace_manager.bind("relators", "http://id.loc.gov/vocabulary/relators/")
        self.base_url = kwargs.get('base_url')
        rules_ttl = kwargs.get("rules_ttl", [])
        if self.metadata_formats_doc.find(
            IslandoraIngester.MODS_XPATH, 
            NS) is not None:
            self.metadataPrefix = "mods"
            self.namespaces = {self.metadataPrefix: str(NS_MGR.mods),
                               "xlink": "http://www.w3.org/1999/xlink"}
            for rule_name in ["bibcat-base.ttl", 
                              "mods-to-bf.ttl"]:
                rules_ttl.append(rule_name)
            self.processor = XMLProcessor(
                rml_rules=rules_ttl,
                base_url=self.base_url,
                triplestore_url=kwargs.get("triplestore_url"),
                institution_iri=kwargs.get("institution_iri"),
                namespaces=self.namespaces)
        else:
            rules_ttl.append(
                os.path.join(BIBCAT_BASE,
                    os.path.join("rdfw-definitions", "bibcat-base.ttl")))
            self.processor = XMLProcessor(
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
        if base_url is None and "base_url" in self.processor.constants:
            base_url = self.processor.constants.get("base_url")
        else:
            raise ValueError("base_url required for __process_mods__")
        instance_url = kwargs.get("instance_url")
        if instance_url is None:
            instance_url = "{0}/{1}".format(base_url, uuid.uuid1())
        try:
            # Check for modsCollection as root element
            mods_xml = etree.XML(mods_result.text)
            mods_collection =  mods_xml.find("mods:modsCollection",
                self.namespaces)
            if mods_collection is None:
                mods_recs = [mods_xml,]
            else:
                mods_recs = mods_collection.findall("mods:mods",
                    self.namespaces)
            for mods_record in mods_recs:
                work_iri = rdflib.URIRef("{}#Work".format(instance_url))
                self.processor.run(mods_record,
                    base_url=base_url,
                    id=uuid.uuid1,
                    item_iri=item_url,
                    instance_iri=instance_url,
                    work_iri=work_iri)
                    
        except ValueError:
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
        sample_size = kwargs.get('sample_size')
        super(IslandoraIngester, self).harvest(
            sample_size=sample_size,
            setSpec=kwargs.get('setSpec'))
        deduplicator = kwargs.get('dedup')
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
            item_url = urllib.parse.urljoin(self.repository,
                "islandora/object/{0}/".format(pid))
            item_uri = rdflib.URIRef(item_url)
            rels_ext, rels_ext_doc = self.__process_rels_ext__(
                item_url=item_url)
            if rels_ext is None:
                continue
            self.__process_mods__(item_url=item_url)
            instance_uri = self.processor.output.value(
                subject=item_uri,
                predicate=NS_MGR.bf.itemOf)
            work_uri = self.processor.output.value(
                subject=instance_uri,
                predicate=NS_MGR.bf.instanceOf)
            rels_ext.run(rels_ext_doc,
                instance_iri=instance_uri,
                work_iri=work_uri)
            self.processor.output += rels_ext.output
            if deduplicator:
                deduplicator.run(self.processor.output,
                    kwargs.get("dedup_classes"))
            logging.info(" processed {}, triples count {:,}".format(
                item_url, 
                len(self.processor.output)))
            self.repo_graph += self.processor.output
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

class LunaIngester(OAIPMHIngester):
    """Harvests Luna objects from a OAI-PMH feed"""
    
    def __init__(self, **kwargs):
        super(LunaIngester, self).__init__(**kwargs)
        self.processor = XMLProcessor(
            triplestore_url=kwargs.get("triplestore_url"),
            base_url=kwargs.get("base_url"),
            rml_rules=["bibcat-base.ttl", 
                       "oai-pmh-dc-xml-to-bf.ttl"],
            namespaces=NS)

    def harvest(self, **kwargs):
        deduplicator = kwargs.get('dedup')
        start = datetime.datetime.utcnow()
        msg = "Starting OAI-PMH harvest of PIDS from Luna at {}".format(
            start)
        try:
            click.echo(msg)
        except io.UnsupportedOperation:
            print(msg)
        count, token = self.__init_doc__(**kwargs)
        while token is not None:
            params = { "resumptionToken": token.text,
                       "verb": "ListRecords"}
            continue_url = "{0}?{1}".format(
                self.oai_pmh_url,
                urllib.parse.urlencode(params))
            shard_result = requests.get(continue_url)
            shard_doc = etree.XML(shard_result.text.encode())
            token = shard_doc.find("oai_pmh:ListRecords/oai_pmh:resumptionToken", NS)
            records = shard_doc.findall("oai_pmh:ListRecords/oai_pmh:record", NS)
            for rec in records:
                self.processor.run(rec, **kwargs)
                if deduplicator is not None:
                    deduplicator.run(self.processor.output)
                self.repo_graph += self.processor.output
                if not count%10 and count > 0:
                    try:
                        click.echo(".", nl=False)
                    except io.UnsupportedOperation:
                         print(".", end="")
                if not count%100:
                    try:
                        click.echo(count, nl=False)
                    except io.UnsupportedOperation:
                         print(count, end="")
                count += 1
                end = datetime.datetime.utcnow()
            if count > 8000:
                print(token.text, count)

