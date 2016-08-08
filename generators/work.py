"""BIBFRAME 2.0 Work Generator


"""
import rdflib
import requests
try:
    from .generator import Generator, new_graph, NS_MGR
    from .sparql import DELETE_WORK_BNODE 
    from .sparql import  FILTER_WORK_TITLE, GET_AVAILABLE_INSTANCES
    from .sparql import GET_INSTANCE_CREATOR, GET_INSTANCE_TITLE
    from .sparql import GET_INSTANCE_WORK_BNODE_PROPS
except SystemError:
    try:
        from generator import Generator, new_graph, NS_MGR
        from sparql import DELETE_WORK_BNODE 
        from sparql import FILTER_WORK_TITLE, GET_AVAILABLE_INSTANCES
        from sparql import GET_INSTANCE_CREATOR, GET_INSTANCE_TITLE
        from sparql import GET_INSTANCE_WORK_BNODE_PROPS
    except ImportError:
        pass


__author__ = "Jeremy Nelson, Mike Stabile"


class WorkGenerator(Generator):
    """Queries BIBFRAME 2.0 triplestore for Instances with missing Works or
    works that are blank nodes, and first attempts to resolve the Instance to
    an existing Work and ifGET_INSTANCE_WORK_BNODE_PROPS that fails, creates a new BIBFRAME Work based the
    Instance's information."""


    def __init__(self, **kwargs):
        """

        Keywords:
            url (str):  URL for the triplestore, defaults to localhost
                        Blazegraph instance
        """
        self.rules = rdflib.Graph()
        self.matched_works = []
        self.processed = []
        super(WorkGenerator, self).__init__(**kwargs)

    def __copy_instance_to_work__(self, instance_uri, work_uri):
        """Method takes an instance_uri and work_uri, copies all of the 
        properties in any bf:Work blank nodes in the instance to the work_uri,
        and then deletes the bf:Work blank node and properties from the 
        instance_uri.

        Args:
            instance_uri(rdflib.URIRef): URI of Instance
            work_uri(rdflib.URIRef): URI of Work
        """
        work_properties_result = requests.post(
            self.triplestore_url,
            data={"query": GET_INSTANCE_WORK_BNODE_PROPS.format(instance_uri),
                  "format": "json"})
        work_properties_bindings = work_properties_result.json()\
             .get("results").get("bindings")
        work_graph = new_graph()
        for row in work_properties_bindings:
            predicate = rdflib.URIRef(row.get("pred").get("value"))
            
            obj_type = row.get("obj").get("type")
            obj_raw_val = row.get("obj").get("value")
            if obj_type.startswith("literal"):
                obj_ = rdflib.Literal(obj_raw_val)
            else:
                obj_ = rdflib.URIRef(obj_raw_val)
            work_graph.add((work_uri, predicate, obj))
        update_result = requests.post(
            self.triplestore_url,
            data={"query": work_graph.serialize(format='turtle')},
            headers={"Content-Type": "text/turtle"})
        # Now remove existing BNode's properties from the BF Instance
        delete_result = requests.post(
            self.triplestore_url,
            data={"query": DELETE_WORK_BNODE.format(instance_uri),
                  "format": "json"})
                 
            

       


    def __generate_work__(self, instance_uri):
        """Internal method takes an BIBFRAME Instance URI, queries triplestore
        for matches based on the loaded rules.

        Args:
            instance_uri(str): URI of BIBFRAME Instance
        Returns:
            rdflib.URIRef: New or existing Work URI
        """
        work_uri = None
        self.matched_works = []
        self.__similiar_titles__(instance_uri)
        self.__similiar_creators__(instance_uri)
        candidate_works = list(set(self.matched_works))
        if len(candidate_works) < 1:
            work_uri = self.__generate_uri__()
            work_graph = new_graph()
            work_graph.add((work_uri, NS_MGR.rdf.type, NS_MGR.bf.Work))
        return work_uri


    def __similiar_creators__(self, uri):
        """Takes an BF Instance URI, extracts creator info and then
        queries triplestore for similar works with the same creator

        Args:
            uri(str): URI of BIBFRAME Instance

        """
        instance_creator_result = requests.post(
            self.triplestore_url,
            data={"query": GET_INSTANCE_CREATOR.format(uri),
                  "format": "json"})
        instance_creator_bindings = instance_creator_result.json()\
            .get("results").get("bindings")
        for row in instance_creator_bindings:
            creator_name = row.get("name").get("value")
            work_creator_result = requests.post(
                self.triplestore_url,
                data={"query": FILTER_WORK_CREATOR.format(creator_name),
                      "format": "json"})
            work_creator_bindings = work_creator_result.json()\
                .get("results").get("bindings")
            if len(work_creator_bindings) < 1:
                continue
            for work_row in work_creator_bindings:
                self.matched_works.append(work_row.get("work").get("value"))



    def __similiar_titles__(self, uri):
        """Takes an BF Instance URI, extracts titles info and then
        queries triplestore for similar works with the same title

        Args:
            uri(str): URI of BIBFRAME Instance
        """
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
                self.matched_works.append(work_row.get("work").get("value"))


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
            instance_url =  row.get('instance').get('value')
            work_uri = self.__generate_work__(instance_url)
            self.__copy_instance_to_work__(
                rdflib.URIRef(instance_url), 
                work_uri)
            

    def run(self):
        """Runs work generator on triplestore"""

        self.harvest_instances()
