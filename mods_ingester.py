"""MODS to BIBFRAME 2.0 command-line ingester"""
__author__ = "Jeremy Nelson, Mike Stabile"


import datetime
import click
import inspect
import logging
import pymarc
import os
import rdflib
import requests
import sys
import uuid

import 

from collections import OrderedDict
from ingester import add_admin_metadata, add_admin_metadata, new_graph 
from ingester import BF, KDS, RELATORS, SCHEMA
sys.path.append(
    os.path.split(os.path.abspath(os.curdir))[0])
from instance import config

# get the current file name for logs and set logging level
MNAME = inspect.stack()[0][1]
MLOG_LVL = logging.DEBUG
logging.basicConfig(level=logging.DEBUG)

MODS2BIBFRAME = None

@click.command()
@click.option("--url", default=None)
@click.option("--filepath", default=None)
def process(url, filepath):
    if url:
        http_result = requests.get(url)
        if http_result.status_code > 399:
            raise ValueError("HTTP Error %s".format(http_result.status_code))
        raw_xml = http_result.text
    
    pass

def setup():
    # setup log
    lg = logging.getLogger("%s-%s" % (MNAME, inspect.stack()[0][3]))
    lg.setLevel(MLOG_LVL)
    
    global MODS2BIBFRAME
    
    MODS2BIBFRAME = new_graph()
    mods2bf_filepath = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                    "rdfw-definitions",
                                    "kds-bibcat-mods-ingestion.ttl")
    lg.debug("MODS2BIBFRAME: %s\nmarc2bf_filepath: %s", 
             MODS2BIBFRAME,
             mods2bf_filepath)
    MODS2BIBFRAME.parse(mods2bf_filepath, format="turtle")

if __name__ == "__main__":
    if not MODS2BIBFRAME:
        setup()
    process()
