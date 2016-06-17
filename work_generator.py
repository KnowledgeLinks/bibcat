"""BIBFRAME 2.0 Work Generator


"""
__author__ = "Jeremy Nelson, Mike Stabile"

import rdflib
import requests

class WorkGenerator(object):

    def __init__(self, **kwargs):
        """
        
        Keywords:
            url (str):  URL for the triplestore, defaults to localhost 
                        Blazegraph instance
        """
        self.triplestore_url = kwargs.get(
            "url", 
            "http://localhost:8080/blazegraph/sparql")
        
    def __harvest_instances__(self):
        """
        Harvests all BIBFRAME Instances that do not have an isInstanceOf
        property.
        """
        pass
        
        
