"""Helper Class and Functions for resolving Library Linked Data Carriers"""
__author__ = "Jeremy Nelson, Mike Stabile"

import os
from linker import Linker, LinkerError, PROJECT_BASE, new_graph 

CARRIERS = new_graph()
ttl_file_path =os.path.join(
    os.path.join(PROJECT_BASE, "bibcat", "rdf-references"),
    "bc_carriers.ttl")
with open(ttl_file_path) as fo:
    CARRIERS.parse(fo, format='turtle') 


class CarrierLinker(Linker):
    """Links existing Library of Congress Carrier Types to BF Instance"""

    def __init__(self, **kwargs):
        super(CarrierLinker, self).__init__(**kwargs)


    def run(self):
        """Method runs the linker on existing triplestore"""
        result = requests.post(self.triplestore_url,
            data={"query": CARRIER_SPARQL,
                  "format": "json"})
        if result.status_code > 399:
            raise LinkerError("CARRIER_SPARQL failed on {}".format(
                self.triplestore_url),
                "HTTP status={}\n{}".format(result.status_code,
                                            result.text))

        bindings 
        
        
CARRIER_SPARQL = Linker.NS.prefix() + """

SELECT ?instance ?value
WHERE {
    ?instance bf:carrier ?carrier .
    ?carrier rdf:type bf:Carrier .
    ?carrier rdf:value ?value 
    filter isBlank(?carrier)
}"""
