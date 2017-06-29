"""Progressive Technology Federal Systems, Inc XML to BIBFRAME 2.0 Ingester"""
__author__ = "Jeremy Nelson"

try:
    from ingesters.xml import XMLIngester
except ImportError:
    from .xml import XMLIngester

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

    def transform(self, xml=None, instance_uri=None, item_uri=None):
        """Overrides parent class transform and adds XML-specific
        transformations

        Args:
            xml(xml.etree.ElementTree.XML): XML or None
            instance_uri: URIRef for instance or None
            item_uri: URIREf for item or None
        """
        super(PTFSIngester, self).transform(
            xml=xml,
            instance_uri=instance_uri,
            item_uri=item_uri)
