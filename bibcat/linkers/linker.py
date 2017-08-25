"""Helper module for linking existing BIBFRAME resources to external data
sources like Library of Congress, DBPedia, VIAF, and others."""

__author__ = "Jeremy Nelson, Mike Stabile"

import os
import rdflib
import sys
BIBCAT_BASE = os.path.abspath(
    os.path.split(
        os.path.dirname(__file__))[0])


class Linker(object):
    """Base Linker class for all other linker classes"""

    def __init__(self, **kwargs):
        self.triplestore_url = kwargs.get(
            "triplestore_url",
            "http://localhost:9999/blazegraph/sparql")


    def run(self):
        pass

class LinkerError(Exception):
    """Custom Error for Linker Classes"""

    def __init__(self, value, details):
        self.value = value
        self.details = details

    def __str__(self):
        return repr(self.value)
