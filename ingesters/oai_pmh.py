"""OAI-PMH to BIBFRAME 2.0 command-line ingester"""
__author__ = "Jeremy Nelson, Mike Stabile"
import datetime
import logging
import xml.etree.ElementTree as etree
import click
import rdflib

from ingesters.dc import DCIngester

class OAIPMHIngester(DCIngester):

    def __init__(self, **kwargs):
        self.oai_pmh_url = kwargs.get("oai_pmh")
        super(OAIPMHIngester, self).__init__(kwargs)

    

