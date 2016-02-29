import requests
import copy
from rdfframework import get_framework as rdfw
from rdfframework.utilities import fw_config, make_triple, iri, uri,\
        is_not_null, render_without_request, pp
DEBUG = True

def get_data(obj, **kwargs):
    ''' queries that datastore for the based on the supplied arguments '''
    _sparql = create_data_sparql_query(obj, **kwargs)
    data = run_sparql_query(_sparql, **kwargs)
    return data
    
def run_sparql_query(sparql, **kwargs):
    ''' run the passed in sparql query and returns the results '''
    _prefix = rdfw().get_prefix()
    if sparql is not None:
        _results = requests.post(fw_config().get('TRIPLESTORE_URL'),
                                 data={"prefix": _prefix,
                                       "query": sparql,
                                       "format": "json"})
        return _results.json().get('results', {}).get('bindings', [])
    else:
        return None
    
def create_data_sparql_query(obj, **kwargs):
    ''' generates the sparql query for getting an object's data '''
    
    subject_uri = kwargs.get("subject_uri", obj.data_subject_uri)
    _class_uri = kwargs.get("class_uri", obj.data_class_uri)
    _lookup_class_uri = _class_uri
    _sparql_args = None
    _sparql_constructor = copy.deepcopy(obj.dependancies)
    if DEBUG:
        print("+++++++++++++++++++++++ Dependancies:")
        pp.pprint(_sparql_constructor)
    _base_subject_finder = None
    _linked_class = None
    _linked_prop = False
    _sparql_elements = []
    _subform_data = {}
    _data_list = obj.is_subobj
    _parent_field = None
    if is_not_null(subject_uri):
        # find the primary linkage between the supplied subjectId and
        # other form classes
        for _rdf_class in _sparql_constructor:
            for _prop in _sparql_constructor[_rdf_class]:
                try:
                    if _class_uri == _prop.get("kds_classUri"):
                        _sparql_args = _prop
                        _linked_class = _rdf_class
                        _sparql_constructor[_rdf_class].remove(_prop)
                        if _rdf_class != _lookup_class_uri:
                            _linked_prop = True
                except:
                    pass
        # generate the triple pattern for linked class
        if DEBUG:
            print("+++++++++++++++++++++++ SPARQL Constructor")
            pp.pprint(_sparql_constructor)
            pp.pprint(obj.dependancies)
        if _sparql_args:
            # create a binding for multi-item results
            if _data_list:
                _list_binding = "BIND(?classID AS ?itemID) ."
            else:
                _list_binding = ''
            # provide connection triples for the id subject and associated
            # rdf class
            _base_subject_finder = \
                    "BIND({} AS ?baseSub) .\n\t{}\n\t{}\n\t{}".format(
                        iri(subject_uri),
                        make_triple("?baseSub",
                                    "a",
                                    iri(uri(_lookup_class_uri))),
                        make_triple("?classID",
                                    iri(uri(_sparql_args.get("kds_propUri"))),
                                    "?baseSub"),
                        _list_binding)
           # if there is a linkage between subject_uri and another associated
           # property in object
            if _linked_prop:
                # create a binding for multi-item results
                if _data_list:
                    _list_binding = "BIND(?s AS ?itemID) ."
                else:
                    _list_binding = ''
                _sparql_elements.append(\
                        "BIND({} AS ?baseSub) .\n\t{}\n\t{}\n\t{}\n\t?s ?p ?o .".format(\
                                iri(subject_uri),
                                make_triple("?baseSub",
                                            "a",
                                            iri(uri(_lookup_class_uri))),
                                make_triple("?s",
                                            iri(uri(_sparql_args.get("kds_propUri"))),
                                            "?baseSub"),
                                _list_binding))
        # iterrate though the classes used in the object and generate the
        # spaqrl triples to pull the data for that class
        for _rdf_class in _sparql_constructor:
            if _rdf_class == _class_uri:
                if _data_list:
                    _list_binding = "BIND(?s AS ?itemID) ."
                else:
                    _list_binding = ''
                _sparql_elements.append(\
                        "\tBIND({} AS ?s) .\n\t{}\n\t{}\n\t?s ?p ?o .".format(
                            iri(subject_uri),
                            make_triple("?s", "a", iri(uri(_lookup_class_uri))),
                            _list_binding))
            for _prop in _sparql_constructor[_rdf_class]:
                if _rdf_class == _class_uri:
                    if _data_list:
                        _list_binding = "BIND(?s AS ?itemID) ."
                    else:
                        _list_binding = ''
                    #_sparql_elements.append("\t"+make_triple(iri(str(\
                            #subject_uri)), iri(_prop.get("propUri")), "?s")+\
                            # "\n\t?s ?p ?o .")
                    _sparql_arg = "\tBIND({} AS ?baseSub) .\n\t{}\n\t{}\n\t{}\n\t?s ?p ?o .".format(\
                            iri(subject_uri),
                            make_triple("?baseSub",
                                        "a",
                                        iri(uri(_lookup_class_uri))),
                            make_triple("?baseSub",
                                        iri(uri(_prop.get("kds_propUri"))),
                                        "?s"),
                            _list_binding)
                    _sparql_elements.append(_sparql_arg)
                elif _rdf_class == _linked_class:
                    _sparql_elements.append(
                        "\t{}\n\t{}\n\t?s ?p ?o .".format(
                            _base_subject_finder,
                            make_triple("?classID",
                                        iri(uri(_prop.get("kds_propUri"))),
                                        "?s")
                            )
                        )


                '''**** The case where an ID looking up a the triples for
                    a non-linked related is not functioning i.e. password
                    ClassID not looking up person org triples if the org
                    class is not used in the form. This may not be a
                    problem ... the below comment out is a start to solving
                     if it is a problem

                    elif _linked_class != self.get_class_name(prop.get(\
                            "classUri")):
                    _sparql_elements.append(
                        "\t" +_base_subject_finder + "\n " +
                        "\t"+ make_triple("?classID", iri(prop.get(\
                                "propUri")), "?s") + "\n\t?s ?p ?o .")'''

        # merge the sparql elements for each class used into one combined
        # sparql union statement
        _sparql_unions = "{{\n{}\n}}".format("\n} UNION {\n".join(\
                _sparql_elements))
        if _data_list:
            _list_binding = "?itemID"
        else:
            _list_binding = ''
        # render the statment in the jinja2 template
        _sparql = render_without_request("sparqlItemTemplate.rq",
                                         prefix=rdfw().get_prefix(),
                                         query=_sparql_unions,
                                         list_binding=_list_binding)
        if DEBUG:
            print("SPARQL query")
            print(_sparql)
        return _sparql
                                         
def query_select_options(field):
    ''' returns a list of key value pairs for a select field '''
    _prefix = rdfw().get_prefix()
    _select_query = field.kds_fieldType.get('kds_selectQuery', None)
    _select_list = {}
    _options = []
    if _select_query:
        # send query to triplestore
        _select_list = requests.post(
            fw_config().get('TRIPLESTORE_URL'),
            data={"query": _prefix + _select_query,
                  "format": "json"})
        _raw_options = _select_list.json().get('results', {}).get('bindings', [])
        _bound_var = field.kds_fieldType.get('kds_selectBoundValue', ''\
                ).replace("?", "")
        _display_var = field.kds_fieldType.get('kds_selectDisplay', ''\
                ).replace("?", "")
        # format query result into key value pairs
        for row in _raw_options:
            _options.append(
                {
                    "id":iri(row.get(_bound_var, {}).get('value', '')),
                    "value":row.get(_display_var, {}).get('value', '')
                })
    return _options
    
def save_file_to_repository(data, repo_item_address):
    ''' saves a file from a form to a repository'''
    object_value = ""
    if repo_item_address:
        print("~~~~~~~~ write code here")
    else:
        repository_result = requests.post(
            fw_config().get("REPOSITORY_URL"),
            data=data.read(),
			         headers={"Content-type":"'image/png'"})
        object_value = repository_result.text
    return iri(object_value)