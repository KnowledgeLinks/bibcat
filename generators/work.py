"""BIBFRAME 2.0 Work Generator


"""
import rdflib
import requests
try:
    from .generator import Generator, new_graph, NS_MGR
    from .sparql import DELETE_WORK_BNODE 
    from .sparql import FILTER_WORK_CREATOR, FILTER_WORK_TITLE 
    from .sparql import GET_AVAILABLE_INSTANCES, GET_INSTANCE_CREATOR 
    from .sparql import GET_INSTANCE_TITLE, GET_INSTANCE_WORK_BNODE_PROPS
except SystemError:
    try:
        from generator import Generator, new_graph, NS_MGR
        from sparql import DELETE_WORK_BNODE 
        from sparql import FILTER_WORK_CREATOR, FILTER_WORK_TITLE 
        from sparql import GET_AVAILABLE_INSTANCES, GET_INSTANCE_CREATOR
        from sparql import GET_INSTANCE_TITLE, GET_INSTANCE_WORK_BNODE_PROPS
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
        self.processed = {}
        self.creator_codes = kwargs.get(
            'creator_codes', 
            ['aus', 'aut', 'cre'])
        super(WorkGenerator, self).__init__(**kwargs)

    def __add_creators__(self, work_graph, work_uri, instance_uri):
        """Method takes a new work graph and instance uri, queries for
        relators:creators of instance uri and adds values to work graph
        
         Args:
            work_graph(rdflib.Graph): RDF Graph of new BF Work
            instance_uri(rdflib.URIRef): URI of BF Instance
        """
        instance_key = str(instance_uri)
        if instance_key in self.processed: 
            for code in self.creator_codes:
                if not code in self.processed[instance_key]:
                    continue
                relator = getattr(NS_MGR.relators, code)
                for agent_uri in self.processed[instance_key][code]:
                    work_graph.add((work_uri, 
                                    relator, 
                                    agent_uri))


    def __add_work_title__(self, work_graph, work_uri, instance_uri):
        """Method takes a new work graph and instance uri, queries for
        bf:InstanceTitle of instance uri and adds values to work graph

        Args:
            work_graph(rdflib.Graph): RDF Graph of new BF Work
            instance_uri(rdflib.URIRef): URI of BF Instance
        """
        instance_key = str(instance_uri)
        if instance_key in self.processed and\
        "title" in self.processed[instance_key]:
            work_title_bnode = rdflib.BNode()
            work_graph.add((work_uri,  NS_MGR.bf.title, work_title_bnode))
            work_graph.add((work_title_bnode, 
                            NS_MGR.rdf.type, 
                            NS_MGR.bf.WorkTitle))
            for row in self.processed[instance_key]["title"]:
                main_title, subtitle = row["mainTitle"], row["subtitle"]
                work_graph.add((work_title_bnode,
                                NS_MGR.bf.mainTitle,
                                rdflib.Literal(main_title)))
                if subtitle:
                    work_graph.add((work_title_bnode,
                                    NS_MGR.bf.subtitle,
                                    rdflib.Literal(subtitle)))
                
       

    def __copy_instance_to_work__(self, instance_uri, work_uri):
        """Method takes an instance_uri and work_uri, copies all of the 
        properties in any bf:Work blank nodes in the instance to the work_uri,
        and then deletes the bf:Work blank node and properties from the 
        instance_uri.

        Args:
            instance_uri(rdflib.URIRef): URI of Instance
            work_uri(rdflib.URIRef): URI of Work
        """
        if instance_uri == work_uri:
            raise ValueError(
                "Instance and Work URIs cannot match uri={}".format(
                    instance_uri))
        work_properties_result = requests.post(
            self.triplestore_url,
            data={"query": GET_INSTANCE_WORK_BNODE_PROPS.format(instance_uri),
                  "format": "json"})
        work_properties_bindings = work_properties_result.json()\
             .get("results").get("bindings")
        work_graph = new_graph()
        work_graph.add((instance_uri, NS_MGR.bf.instanceOf, work_uri))
        for row in work_properties_bindings:
            predicate = rdflib.URIRef(row.get("pred").get("value"))
            obj_type = row.get("obj").get("type")
            obj_raw_val = row.get("obj").get("value")
            if obj_type.startswith("literal"):
                if predicate == rdflib.RDF.type:
                    # Skip all literals 
                    continue
                obj_ = rdflib.Literal(obj_raw_val)
            else:
                obj_ = rdflib.URIRef(obj_raw_val)
            work_graph.add((work_uri, predicate, obj_))
        self.__add_work_title__(work_graph, work_uri, instance_uri)
        self.__add_creators__(work_graph, work_uri, instance_uri)
        print(work_graph.serialize(format='turtle').decode())
        update_result = requests.post(
            self.triplestore_url,
            data=work_graph.serialize(format='turtle'),
            headers={"Content-Type": "text/turtle"})
        # Now remove existing BNode's properties from the BF Instance
        delete_result = requests.post(
            self.triplestore_url,
            data=DELETE_WORK_BNODE.format(instance_uri),
            headers={"Content-Type": "application/sparql-update"})
        if delete_result.status_code > 399:
            raise ValueError("Cannot Delete Work blank nodes for {}\n{}".format(
                instance_uri, delete_result.text))
      


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
        elif len(candidate_works) == 1:
            work_uri = rdflib.URIRef(candidate_works[0])
        return work_uri


    def __similiar_creators__(self, uri):
        """Takes an BF Instance URI, extracts creator info and then
        queries triplestore for similar works with the same creator

        Args:
            uri(str): URI of BIBFRAME Instance

        """
        for code in self.creator_codes:
            sparql = GET_INSTANCE_CREATOR.format(
                        uri,
                        getattr(NS_MGR.relators, code))
            instance_creator_result = requests.post(
                self.triplestore_url,
                data={"query": sparql,
                      "format": "json"})
            instance_creator_bindings = instance_creator_result.json()\
                .get("results").get("bindings")
            for row in instance_creator_bindings:
                creator_name = row.get("name").get("value")
                creator_uri = rdflib.URIRef(row.get("creator").get("value"))
                instance_key = str(uri)
                if instance_key in self.processed:
                    if code in self.processed[instance_key]:
                        self.processed[instance_key][code].append(
                            creator_uri)
                    else:
                        self.processed[instance_key][code] = [
                            creator_uri,]
                else:
                    self.processed[instance_key] = {code: [
                            creator_uri,]}
                     
                work_creator_result = requests.post(
                    self.triplestore_url,
                    data={"query": FILTER_WORK_CREATOR.format(creator_name),
                          "format": "json"})
                work_creator_bindings = work_creator_result.json()\
                .get("results").get("bindings")
                if len(work_creator_bindings) < 1:
                    continue
                for work_row in work_creator_bindings:
                    self.matched_works.append(
                        work_row.get("work").get("value"))



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
            if uri in self.processed and "title" in self.processed[uri]:
                self.processed[uri]["title"].append(
                    {"mainTitle": main_title,
                     "subtitle": subtitle})
            else:
                self.processed[uri] = {"title": [{"mainTitle": main_title,
                                                  "subtitle": subtitle}]}
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
