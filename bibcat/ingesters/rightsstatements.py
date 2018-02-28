from bs4 import BeautifulSoup
import urllib
import rdflib
import threading
import queue

def get_rdf():
    """
    Returns serialized data for statements from 'http://rightsstatements.org/'
    """
    def worker(statement):
        print("-> Getting: ", statement)
        s_page = urllib.request.urlopen(statement)
        raw = s_page.read().decode()
        json_ld = raw[raw.find("{",
                               raw.find('ld+json">')):raw.find('</script>')]
        print("-> Retrieved:", statement, " Lenght: ", len(statement))
        data_list.append(json_ld)

    url = "http://rightsstatements.org/page/1.0/?language=en"
    page = urllib.request.urlopen(url)
    soup = BeautifulSoup(page, 'html.parser')
    statement_pages =[div.find("a").text
                      for div in soup.find_all('div',
                                               attrs={'class':"statement-box"})]
    print("Retrieved '%s' statement links" % len(statement_pages))
    threads = []
    data_list = []
    graph = rdflib.Graph()
    for statement in statement_pages:
        graph.add((rdflib.URIRef(statement),
            rdflib.RDF.type,
            rdflib.URIRef('http://id.loc.gov/ontologies/bibframe/UsePolicy')))
        t = threading.Thread(target=worker, args=(statement,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()
    print("All threads finished")
    print("Parsing data")
    for data in data_list:
        graph.parse(data=data, format='json-ld')

    print("Data parsed")
    return graph.serialize(format='nt').decode()

