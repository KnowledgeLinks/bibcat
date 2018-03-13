from bs4 import BeautifulSoup
import urllib, pdb
import rdflib
import threading
import queue
import lxml.etree
from rdfframework.configuration import RdfConfigManager
from rdfframework.connections import ConnManager
from rdfframework.datatypes import Uri, XsdString
__CFG__ = RdfConfigManager()
__CONNS__ = ConnManager()

def get_rdf():
    """
    Returns serialized data for statements from 'http://rightsstatements.org/'
    """
    def worker(idx, item, marc2bibframe2, nsm, output):
        print("-> Getting: ", item)
        url = item['collection']['value'] + "/download_mods_as_marcxml"
        iri = Uri(item['collection']['value'])
        org = Uri(item['org']['value'])
        s_page = urllib.request.urlopen(url)
        raw = s_page.read()
        try:
            raw_xml = lxml.etree.XML(raw)
        except lxml.etree.XMLSyntaxError:
            return
        bf_rdf_xml = marc2bibframe2(raw_xml)
        raw_rdf_xml = lxml.etree.tostring(bf_rdf_xml)
        bf_rdf = rdflib.Graph()
        bf_rdf.parse(data=raw_rdf_xml.decode().replace("  ",""), format='xml')
        # graph.add((iri.rdflib, nsm.rdf.type.rdflib, nsm.bf.Collection))
        # graph.add((iri.rdflin, nsm.bf.heldBy.rdflib, org.rdflib))
        sparql = """
                CONSTRUCT
                {{
                    {subj} a bf:Collection .
                    {subj} bf:title ?bnTitle .
                    ?bnTitle ?bnTitleP ?bnTitleO .
                    {subj} bf:heldBy {org} .
                }}
                WHERE
                {{
                    # Find the longest title label blank node
                    {{
                        SELECT ?bnTitle
                        {{
                            OPTIONAL {{?s a bf:Instance .}}
                            OPTIONAL {{?s a bf:Collection .}}
                            ?s bf:title ?bnTitle .
                            ?bnTitle ?p ?o.
                            ?bnTitle rdfs:label ?label .
                            BIND(STRLEN(?label) as ?labelLen)
                        }}
                        ORDER BY DESC(?labelLen)
                        LIMIT 1
                    }}
                    ?bnTitle ?bnTitleP ?bnTitleO .
                    FILTER(!(STRSTARTS(STR(?bnTitleP),
                                     "http://id.loc.gov/ontologies/bflc/")))
                }}""".format(subj=iri.sparql, org=org.sparql)
        new_data = bf_rdf.query(sparql).serialize(format='turtle').decode()
        output[idx] = new_data
        print("-> Retrieved: ", item)

    marc2bibframe2 = lxml.etree.XSLT(\
            lxml.etree.parse(__CFG__.MARC2BIBFRAME2_XSLT))
    # Look for missing collection urls
    qry = """prefix bf: <http://id.loc.gov/ontologies/bibframe/>
             select distinct ?collection ?org
             {
                 ?work bf:partOf ?collection .
                 OPTIONAL { ?collection ?p ?o .}
                 filter(!bound(?o))
                 ?instance bf:instanceOf ?work .
                 ?item bf:itemOf ?instance .
                 ?item bf:heldBy ?org
             }"""
    url_list = __CONNS__.datastore.query(qry)
    results = [None for item in url_list]
    threads = []
    for i, item in enumerate(url_list):
        # worker(i, item, marc2bibframe2, __CFG__.nsm, results)
        t = threading.Thread(target=worker,
                             args=(i,
                                   item,
                                   marc2bibframe2,
                                   __CFG__.nsm,
                                   results))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()
    for i, val in enumerate(results):
        if val:
            __CONNS__.datastore.load_data(data=val, format='ttl')
        else:
            print("failed to find: ", url_list[i])
    print("All searching finished")


def get_other_rdf():
    """
    The digital collections library does not have a source feed. Looking at t
    the source page for the URIs there is a JSON variable that contains all of
    the collection listings. That data is saved into the Plains2Peak sample
    folder.

    This function will convert that data to Bibframe and upload it to the
    triplestore
    """

    def make(obj):
        """
        Creates the triples for loading into the triplestore

        Args:
        -----
            obj: the dictionary to parse
        """
        uri = Uri("http://digitalcollections.uwyo.edu/luna/servlet/" + \
                  obj['id']).sparql
        name = XsdString(obj['collectionName']).sparql
        heldby = Uri("<http://www.uwyo.edu/ahc/>").sparql
        triples = """
            {uri} a bf:Collection ;
                bf:title [
                    a bf:Title ;
                    bf:mainTitle {name} ;
                    rdfs:label {name}
                ] ;
            bf:heldBy {heldby} .
            """.format(uri=uri, name=name, heldby=heldby)
        return triples

    filepath = __CFG__.WYCOLLECTIONS
    if not filepath:
        print("Collections not loaded. JSON file path not found")
    with open(filepath) as fo:
        raw = fo.read()
    data = json.loads(raw)
    turtle_data = "%s\n%s" % (dm.cfg.nsm.prefix('turtle'),
                              "".join([make(item) for item in data]))
