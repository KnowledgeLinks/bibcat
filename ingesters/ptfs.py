"""Progressive Technology Federal Systems, Inc XML to BIBFRAME 2.0 Ingester"""
__author__ = "Jeremy Nelson"

import logging
import xml.etree.ElementTree as etree

from ingesters.ingester import new_graph, NS_MGR
from ingesters.xml import XMLIngester
from ingesters.sparql import GET_ADDL_PROPS

class PTFSIngester(XMLIngester):
    """PTFS XML to BIBFRAME 2.0 Ingester"""

    def __init__(self, **kwargs):
        xml_rules = ["kds-bibcat-ptfs-ingester.ttl"]
        rules = kwargs.get("rules_ttl")
        if isinstance(rules, str):
            xml_rules.append(rules)
        if isinstance(rules, list):
            xml_rules.extend(rules)
        kwargs["rules_ttl"] = xml_rules
        super(PTFSIngester, self).__init__(
            **kwargs)
