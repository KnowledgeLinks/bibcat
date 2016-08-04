"""BIBFRAME 2.0 Work Generator


"""
import rdflib
import requests
try:
    from .generator import Generator, new_graph, NS_MGR
    from .sparql import FILTER_WORK_TITLE, GET_AVAILABLE_INSTANCES
    from .sparql import GET_INSTANCE_TITLE
except SystemError:
    try:
        from generator import Generator, new_graph, NS_MGR
        from sparql import FILTER_WORK_TITLE, GET_AVAILABLE_INSTANCES
        from sparql import GET_INSTANCE_TITLE
    except ImportError:
        pass


__author__ = "Jeremy Nelson, Mike Stabile"


class WorkGenerator(Generator):
    """Queries BIBFRAME 2.0 triplestore for Instances with missing Works or
    works that are blank nodes, and first attempts to resolve the Instance to
    an existing Work and if that fails, creates a new BIBFRAME Work based the
    Instance's information."""


    def __init__(self, **kwargs):
        """

        Keywords:
            url (str):  URL for the triplestore, defaults to localhost
                        Blazegraph instance
        """
        self.rules = rdflib.Graph()
        self.processed = []
        super(WorkGenerator, self).__init__(**kwargs)

    def __generate_work__(self, instance_uri):
        """Internal method takes an BIBFRAME Instance URI, queries triplestore
        for matches based on the loaded rules.

        Args:
            instance_uri(str): URI of BIBFRAME Instance
        Returns:
            str: New or existing Work URI
        """
        work_uri = None
        candidate_works = self.__similiar_titles__(instance_uri)
        if len(candidate_works) < 1:
            work_uri = self.__generate_uri__()
            work_graph = new_graph()
            work_graph.add((work_uri, NS_MGR.rdf.type, NS_MGR.bf.Work))
        return str(work_uri)

    def __similiar_titles__(self, uri):
        """Takes an BF Instance URI, extracts titles info and then
        queries triplestore for similar works with the same title

        Args:
            uri(str): URI of BIBFRAME Instance

        Returns:
            list: List containing all works with similar titles to the
                  BF Instance
        """
        matched_works = []
        instance_title_result = requests.post(
            self.triplestore_url,
            data={"query": GET_INSTANCE_TITLE.format(uri),
                  "format": "json"})
        instance_title_bindings = instance_title_result.json()\
            .get("results").get("bindings")
        for row in instance_title_bindings:
            main_title, subtitle = row.get("mainTitle").get("value"), None
            if "subtitle" in row:
                subtitle = row.get("subtitle").get("value")
            work_title_result = requests.post(
                self.triplestore_url,
                #! Need to add subtitle to SPARQL query
                data={"query": FILTER_WORK_TITLE.format(main_title, subtitle),
                      "format": "json"})
            work_title_bindings = work_title_result.json()\
                .get("results").get("bindings")
            if len(work_title_bindings) < 1:
                continue
            for work_row in work_title_bindings:
                matched_works.append(work_row.get("work").get("value"))
        return matched_works

    def harvest_instances(self):
        """
        Harvests all BIBFRAME Instances that do not have an isInstanceOf
        property.

        #! for performance considerations may need to run sparl query that
        limits the batch size
        """
        result = requests.post(
            self.triplestore_url,
            data={"query": GET_AVAILABLE_INSTANCES,
                  "format": "json"})
        if result.status_code > 399:
            raise ValueError("WorkGenerator failed to query {}".format(
                self.triplestore_url))
        bindings = result.json().get('results').get('bindings')
        for row in bindings:
            self.__generate_work__(row.get('instance').get('value'))

    def run(self):
        """Runs work generator on triplestore"""

        self.harvest_instances()
