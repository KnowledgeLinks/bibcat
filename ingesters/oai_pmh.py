"""OAI-PMH to BIBFRAME 2.0 command-line ingester"""
__author__ = "Jeremy Nelson, Mike Stabile"
import datetime
import logging
import xml.etree.ElementTree as etree
import rdflib
import requests


from .dc import DCIngester
from .mods import MODSIngester

NS = {"oai_pmh": "http://www.openarchives.org/OAI/2.0/"}

class OAIPMHIngester(object):
    IDENT_XPATH = "oai_pmh:ListIdentifiers/oai_pmh:header/oai_pmh:identifier"
    TOKEN_XPATH = "oai_pmh:ListIdentifiers/oai_pmh:resumptionToken"

    def __init__(self, **kwargs):
        self.oai_pmh_url = kwargs.get("oai_pmh")
        rules_ttl = kwargs.get("rules_ttl")
        self.identifiers = []
        self.metadataPrefix = "oai_dc"
        metadata_result = requests.get("{}?verb=ListMetadataFormats".format(self.oai_pmh_url))
        
        #ident_result = "oai_pmh:Identify/oai_pmh:description/oai_ident:oai-identifier/oai_ident:repositoryIdentifier"
        metadata_doc = etree.XML(metadata_result.text)
        # 
        if metadata_doc.find(
            "oai_pmh:ListMetadataFormats/oai_pmh:metadataFormat[oai_pmh:metadataPrefix='mods']", NS):
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
        resume_token = initial_doc.find(OAIPMHIngester.TOKEN_XPATH)
        self.identifiers.extend(
            [r.text for r in initial_doc.findall(OAIPMHIngester.IDENT_XPATH)])
        total_size = int(resume_token.attrib.get("completeListSize", 0))
        while len(self.identifiers) <= total_size:
            continue_url = "{0}?verb=ListIdentifiers&resumptionToken={1}".format(
                self.oai_pmh_url,
                resume_token)
            result = requests.get(continue_url)
            shard_doc = etree.XML(result.text)
            resume_token = shard_doc.find(OAIPMHIngester.TOKEN_XPATH)
            shard_idents = [r.text for r in initial_doc.findall(
                                OAIPMHIngester.IDENT_XPATH)]
            self.identifiers.extend(shard_idents)



            
             
        
