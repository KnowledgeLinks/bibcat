"""BIBFRAME 2.0 Work Generator


"""
import datetime
import rdflib
import requests
try:
    from .generator import Generator, new_graph, NS_MGR
    from .sparql import DELETE_WORK_BNODE 
    from .sparql import FILTER_WORK_CREATOR, FILTER_WORK_TITLE 
    from .sparql import GET_AVAILABLE_INSTANCES, GET_INSTANCE_CREATOR 
    from .sparql import GET_INSTANCE_TITLE, GET_INSTANCE_WORK_BNODE_PROPS
    from .sparql import DELETE_COLLECTION_BNODE, FILTER_COLLECTION
    from .sparql import GET_AVAILABLE_COLLECTIONS
except SystemError:
    try:
        from generator import Generator, new_graph, NS_MGR
        from sparql import DELETE_WORK_BNODE 
        from sparql import FILTER_WORK_CREATOR, FILTER_WORK_TITLE  
        from sparql import GET_AVAILABLE_INSTANCES, GET_INSTANCE_CREATOR
        from sparql import GET_INSTANCE_TITLE, GET_INSTANCE_WORK_BNODE_PROPS
        from sparql import DELETE_COLLECTION_BNODE, FILTER_COLLECTION 
        from sparql import GET_AVAILABLE_COLLECTIONS
    except ImportError:
        pass


__author__ = "Jeremy Nelson, Mike Stabile"


class WorkError(Exception):

    def __init__(self, reason):
        self.reason = reason

    def __str__(self):
        return str(self.reason)

class CollectionGenerator(Generator):
    """Queries triplestore for BIBFRAME 2.0 Instances that are related to
    collections that are blank nodes. Generator reifies Collection as a bf:Work
    with the rdfs:label triple and triples for each bf:Instance."""

    def __init__(self, **kwargs):
        super(CollectionGenerator, self).__init__(**kwargs)

    def __generate_collection__(self, **kwargs):
        
        """Generates new Collection for the Instance in the triplestore

        Keyword args:
           instance(rdflib.URIRef): URI of Instance
           label(rdflib.Literal): Literal string of RDF label
        """
        instance = kwargs.get('instance')
        label = kwargs.get('label')
        if instance is None or label is None:
            raise WorkError("Generate Collection both instance and label")
        collection_uri = self.__generate_uri__()
        collection_graph = new_graph()
        for type_of in [NS_MGR.pcdm.Collection, NS_MGR.bf.Work]:
            collection_graph.add((collection_uri, 
                NS_MGR.rdf.type,
                type_of))
        collection_graph.add((collection_uri,
            NS_MGR.rdfs.label,
            label))
        collection_graph.add((collection_uri,
            NS_MGR.bf.hasPart,
            instance))
        result = requests.post(
            self.triplestore_url,
            data=collection_graph.serialize(format='turtle'),
            headers={"Content-Type": "text/turtle"})
        if result.status_code > 399:
            raise WorkError("Failed to add {} to triplestore".format(
                collection_uri))
        return collection_uri



    def __handle_collections__(self, **kwargs):
        """Queries triplestore for collections to match
        existing organizations with collections matching a label or
        other identification.
        
        Keyword args:
            instance(rdflib.URIRef): URI of Instance
            organization(rdflib.URIRef): URI of Organization
            item(rdflib.URIRef): URI of Item
            rdfs_label(rdflib.Literal): Literal string of RDFS label

        Returns:
            list: List of Collection URIs
        """
        instance = kwargs.get('instance')
        org = kwargs.get('organization')
        item = kwargs.get('item')
        label = kwargs.get('rdfs_label')
        query = FILTER_COLLECTION.format(item, org, label)
        result = requests.post(self.triplestore_url,
                data={"query": query,
                      "format": "json"})
        if result.status_code > 399:
            raise WorkError("Failed to run {}".format(query))
        bindings = result.json().get('results').get('bindings')
        if len(bindings) < 1:
            return [self.__generate_collection__(
                instance=instance,
                label=label),]
        else:
            collections = []
            for row in bindings:
                collection_uri = rdflib.URIRef(
                    row.get('collection').get('value'))
                existing_instance = rdflib.URIRef(
                    row.get('instance').get('value'))
                if existing_instance == instance:
                    continue
                collections.append(collection_uri)
                update_graph = new_graph()
                new_graph.add((collection_uri,
                    NS_MGR.bf.hasPart,
                    instance))
                result = requsts.post(
                    self.triplestore_url,
                    data=new_graph.serialize(format='turtle'),
                    headers={"Content-Type": "text/turtle"})
            return collections

    def run(self):
        """Runs Collection Generator"""
        result = requests.post(self.triplestore_url,
                data={"query": GET_AVAILABLE_COLLECTIONS,
                      "format": "json"})
        if result.status_code > 399:
            raise WorkError("Failed to run sparql query")

        bindings = result.json().get('results').get('bindings')
        for row in bindings:
            instance_uri = rdflib.URIRef(row.get('instance').get('value'))
            org_uri = rdflib.URIRef(row.get('org').get('value'))
            item_uri = rdflib.URIRef(row.get('item').get('value'))
            label = rdflib.Literal(row.get('label').get('value'))
            #! Should check for language in label
            collections = self.__handle_collections__(
                instance=instance_uri, 
                item=item_uri,
                organization=org_uri, 
                rdfs_label=label)
            # Now remove existing BNode's properties from the BF Instance
            delete_result = requests.post(
                self.triplestore_url,
                data=DELETE_COLLECTION_BNODE.format(instance_uri),
                headers={"Content-Type": "application/sparql-update"})
            if delete_result.status_code > 399:
                raise WorkError("Cannot Delete Collection blank nodes for {}\n{}".format(
                    instance_uri, delete_result.text))





class WorkGenerator(Generator):
    """Queries BIBFRAME 2.0 triplestore for Instances with missing Works or
    works that are blank nodes, and first attempts to resolve the Instance to
    an existing Work and ifGET_INSTANCE_WORK_BNODE_PROPS that fails, creates a new BIBFRAME Work based the
    Instance's information."""


    def __init__(self, **kwargs):
        """

        Keyword args:
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
            if 'pred' not in row or 'obj' not in row:
                continue
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
        self.__similar_titles__(instance_uri)
        self.__similar_creators__(instance_uri)
        candidate_works = list(set(self.matched_works))
        if len(candidate_works) < 1:
            work_uri = self.__generate_uri__()
            work_graph = new_graph()
            work_graph.add((work_uri, NS_MGR.rdf.type, NS_MGR.bf.Work))
        else:
            # Takes the top match
            work_uri = rdflib.URIRef(candidate_works[0])
        return work_uri


    def __similar_creators__(self, uri): 
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
                creator_name = row.get("name", {}).get("value")
                creator_url = row.get("creator", {}).get("value")
                if creator_name is None or creator_url is None:
                    continue
                creator_uri = rdflib.URIRef(creator_url)
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



    def __similar_titles__(self, uri):
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
            main_title, subtitle = row.get("mainTitle", {}).get("value"), None
            if main_title is None:
                continue
            if "subtitle" in row:
                subtitle = row.get("subtitle").get("value")
            if uri in self.processed and "title" in self.processed[uri]:
                self.processed[uri]["title"].append(
                    {"mainTitle": main_title,
                     "subtitle": subtitle})
            else:
                self.processed[uri] = {"title": [{"mainTitle": main_title,
                                                  "subtitle": subtitle}]}
            escaped_title = main_title.replace('"', '\"')
            query = FILTER_WORK_TITLE.format(escaped_title)
            work_title_result = requests.post(
                self.triplestore_url,
                #! Need to add subtitle to SPARQL query
                data={"query": query,
                      "format": "json"})
            if work_title_result.status_code > 399:
                print("Error with similar title {}".format(main_title))
            work_title_bindings = work_title_result.json()\
               .get("results").get("bindings")
            if len(work_title_bindings) < 1:
                continue
            for work_row in work_title_bindings:
                self.matched_works.append(work_row.get("work").get("value"))


    def harvest_instances(self):
        """
        Harvests all BIBFRAME Instances that have an Blank Node for the
        isInstanceOf property.
        
        #! for performance considerations may need to run sparql query that
        limits the batch size
        """
        result = requests.post(
            self.triplestore_url,
            data={"query": GET_AVAILABLE_INSTANCES,
                  "format": "json"})
        if result.status_code > 399:
            raise WorkError("WorkGenerator failed to query {}".format(
                self.triplestore_url))
        bindings = result.json().get('results').get('bindings')
        start = datetime.datetime.utcnow()
        print("Started Processing at {} for {} Instances".format(
            start,
            len(bindings)))
        for i, row in enumerate(bindings):
            instance_url =  row.get('instance').get('value')
            work_uri = self.__generate_work__(instance_url)
            self.__copy_instance_to_work__(
                rdflib.URIRef(instance_url), 
                work_uri)
            if not i%10 and i > 0:
                print(".", end="")
            if not i%100:
                print(i, end="")
        end = datetime.datetime.utcnow()
        print("Finished Processing at {}, total time={} mins".format(
            end,
            (end-start).seconds / 60.0))
            


    def run(self):
        """Runs work generator on triplestore"""

        self.harvest_instances()


