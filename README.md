# Knowledgelinks.io BIBCAT 2.0

[![Build Status](https://travis-ci.org/KnowledgeLinks/rdfw-bibcat.svg)](https://travis-ci.org/KnowledgeLinks/rdfw-bibcat)


## Installation
The easiest way to get started with `bibcat` is to install with **pip**:

    pip install bibcat

### Development installation 
You can also clone this repository and run pip from the same directory:

    git clone https://github.com/KnowledgeLinks/rdfw-bibcat bibcat
    cd bibcat
    pip install -e . 

If you don't have pip available (although you should because `bibcat` is targeted for Python 3.5+)
you can also follow the same steps to clone `bibcat` but run `python setup.py install`.    

## Basic Usage

## Running RDF Map Processor
[RDF Mapping Language](http://rml.io/) RDF turtle files provides the mapping between
 different input sources including XML, JSON,  CSV files, and SPARQL endpoints that
we current normalize to a production [BIBFRAME 2.0](http://www.loc.gov/bibframe/docs/index.html)
level of description that also combines other RDF vocabularies for  
RDF-based applications.

### MARC XML to BIBFRAME 2.0 to Production BIBFRAME 2.0

    >>> import lxml.etree
    >>> marc2bibframe_xsl = lxml.etree.parse("{path}/marc2bibframe2/xsl/marc2bibframe2.xsl")
    >>> xsl_transform = lxml.etree.XSLT(marc2bibframe_xsl)
    >>> def bibframe_handler(raw_marc_xml):
	    marc_xml = lxml.etree.XML(raw_marc_xml)
	    bf_xml = xsl_transform(marc_xml, baseuri="'https://bibcat.org/'")
	    bf_rdf = rdflib.Graph().parse(data=lxml.etree.tostring(bf_xml))
	    return bf_rdf

### MODS XML to Production BIBFRAME 2.0

    >>> import uuid
    >>> import lxml.etree
    >>> from bibcat.rml.processor import processor
    >>> base_url = "https://bibcat.org"
    >>> mods_xml = lxml.etree.parse("/filepath/to/mods/file.xml")
    >>> mods2bf = processor.XMLProcessor(
            base_url=base_url,
            triplestore_url="http://localhost:9999/blazegraph/sparql",
            rml_rules=['bibcat-base.ttl', 'mods-to-bf.ttl'])
    >>> mods2bf.run(mods_xml, 
                   instance_iri="{}/{}".format(base_url, uuid.uuid1()),
                   item_iri="{}/test-item".format(base_url))
    >>> mods2bf.output # RDF Graph of BF
                                           

### Dublin Core XML to Production BIBFRAME 2.0

### Production BIBFRAME 2.0 to Schema.org RDF

### Production BIBFRAME 2.0 to DP.LA MAPv4

## Running Islandora, ContentDM&rep;, and Luna&rep; OAI-Harvester
