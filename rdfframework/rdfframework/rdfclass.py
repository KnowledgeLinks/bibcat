__author__ = "Mike Stabile, Jeremy Nelson"

import json
import requests

from werkzeug.datastructures import FileStorage
from jinja2 import Template
from rdfframework.utilities import clean_iri, fw_config, iri, is_not_null, \
    make_list, make_set, make_triple, remove_null, DeleteProperty, \
    NotInFormClass, pp, uri, calculate_default_value

from .getframework import get_framework as rdfw
from rdfframework.rdfdatatype import RdfDataType
from rdfframework.utilities.debug import dumpable_obj
from rdfframework.processors import clean_processors, run_processor
from rdfframework.sparql import save_file_to_repository


class RdfClass(object):
    '''RDF Class for an RDF Class object.
       Used for manipulating and validating an RDF Class subject'''

    def __init__(self, json_obj, class_name):
        self.class_name = None
        self.kds_properties = {}
        for _prop in json_obj:
            setattr(self, _prop, json_obj[_prop])
        setattr(self, "class_name", class_name)

    def save(self, rdf_obj, validation_status=True):
        """Method validates and saves passed data for the class

        Args:
            rdf_obj -- Current RDF Form class fields
            validationS

        valid_required_props = self._validate_required_properties(
            rdf_obj,
            old_form_data)
        validDependancies = self._validate_dependant_props(
            rdf_obj,
            old_form_data)"""
        if not validation_status:
            return self.validate_form_data(rdf_obj)

        save_data = self._process_class_data(rdf_obj)
        #print("-------------- Save data:\n",json.dumps(dumpable_obj(save_data)))
        save_query = self._generate_save_query(save_data)
        return self._run_save_query(save_query)


    def new_uri(self):
        '''*** to be written ***
        generates a new URI
          -- for fedora generates the container and returns the URI
          -- for blazegraph process will need to be created'''
       #print("generating new URI")

    def validate_obj_data(self, rdf_obj, old_data):
        '''This method will validate whether the supplied object data
           meets the class requirements and returns the results'''
        _validation_steps = {}
        _validation_steps['validRequiredFields'] = \
                self._validate_required_properties(rdf_obj, old_data)
        _validation_steps['validPrimaryKey'] = \
                self.validate_primary_key(rdf_obj, old_data)
        _validation_steps['validFieldData'] = \
                self._validate_property_data(rdf_obj, old_data)
        _validation_steps['validSecurity'] =  \
                self._validate_security(rdf_obj, old_data)
        #print("----------------- Validation ----------------------\n", \
                #json.dumps(_validation_steps, indent=4))
        _validation_errors = []
        for step in _validation_steps:
            if _validation_steps[step][0] != "valid":
                for _error in _validation_steps[step]:
                    _validation_errors.append(_error)
        if len(_validation_errors) > 0:
            return {"success": False, "errors":_validation_errors}
        else:
            return {"success": True}

    def validate_primary_key(self, rdf_obj, old_data):
        '''query to see if PrimaryKey is Valid'''
        debug = False
        if old_data is None:
            old_data = {}
        _prop_name_list = []
        if hasattr(self, "kds_primaryKey"):
            pkey = self.kds_primaryKey
            if isinstance(pkey, dict):
                pkey = pkey.get("kds_keyCombo",[])
            pkey = make_list(pkey)
        else:
            pkey = []
        if debug: print(self.kds_classUri, " PrimaryKeys: ", pkey, "\n")
        if len(pkey) < 1:
            return ["valid"]
        else:
            _calculated_props = self._get_calculated_properties()
            _old_class_data = self._select_class_query_data(old_data)
            _new_class_data = {}
            _query_args = [make_triple("?uri", "a", \
                    iri(uri(self.kds_classUri)))]
            _multi_key_query_args = [make_triple("?uri", 
                                                 "a",
                                                 iri(uri(self.kds_classUri)))]
            _key_changed = False
            _prop_uri_list = []
            _key_props = []
            # get primary key data from the form data
            for prop in rdf_obj:
                if prop.kds_propUri in pkey:
                    _new_class_data[prop.kds_propUri] = prop.data
                    _prop_name_list.append(prop.kds_formLabelName)
                    _key_props.append(prop)
        
            for key in pkey:

                _object_val = None
                #get the _data_value to test against
                _data_value = _new_class_data.get(key, _old_class_data.get(key))
                if is_not_null(_data_value):
                    _range_obj = make_list(self.kds_properties[key].get(\
                            "rdfs_range", [{}]))[0]
                    _data_type = _range_obj.get('storageType')
                    _range = _range_obj.get('rangeClass')
                    if debug: print("_data_type: ", _data_type)
                    if _data_type == 'literal':
                        _object_val = RdfDataType(_range).sparql(_data_value)
                    else:
                        _object_val = iri(uri(_data_value))
                else:
                    # if data is missing from the key fields exit method and 
                    # return valid. *** The object value does not exist and 
                    #                   will be generated when another class 
                    #                   is saved
                    return ["valid"]
                # if the old_data is not equel to the newData re-evaluate
                # the primaryKey
                if (_old_class_data.get(key) != _new_class_data.get(key))\
                        and (key not in _calculated_props):
                    _key_changed = True
                    if _object_val:
                        _query_args.append(make_triple("?uri", iri(uri(key)), \
                                _object_val))
                        _multi_key_query_args.append(make_triple("?uri", \
                                iri(uri(key)), _object_val))
                else:
                    if _object_val:
                        _multi_key_query_args.append(make_triple("?uri", \
                                iri(uri(key)), _object_val))
                    else:
                        _key_changed = False
            # if the primary key changed in the form we need to
            # query to see if there is a violation with the new value

            if _key_changed:
                if len(pkey) > 1:
                    args = _multi_key_query_args
                else:
                    args = _query_args
                sparql = '''
                         {}\nSELECT DISTINCT (COUNT(?uri)>0 AS ?keyViolation)
                         {{\n{}\n}}\nGROUP BY ?uri'''.format(\
                                rdfw().get_prefix(),
                                "\n".join(args)) 
                if debug: print("----------- PrimaryKey query:\n", sparql)
                _key_test_results =\
                        requests.post(\
                                fw_config().get('TRIPLESTORE_URL'),
                                data={"query": sparql, "format": "json"})
                if debug: print("_key_test_results: ", _key_test_results.json())
                _key_test = _key_test_results.json().get('results').get( \
                        'bindings', [])
                if debug: print(_key_test)
                if len(_key_test) > 0:
                    _key_test = _key_test[0].get('keyViolation', {}).get( \
                            'value', False)
                else:
                    _key_test = False

                
                if not _key_test:
                    return ["valid"]
                else:
                    error_msg = "This {} aleady exists.".format(
                                        " / ".join(_prop_name_list))
                    for prop in _key_props:
                        if hasattr(prop, "errors"):
                            prop.errors.append(error_msg)
                        else:
                            setattr(prop, "errors", [error_msg])
                    return [{"errorType":"primaryKeyViolation",
                             "formErrorMessage": error_msg,
                             "errorData":{"class": self.kds_classUri,
                                          "propUri": pkey}}]
            return ["valid"]
        '''except:
            return ["valid"]
        else:
            return ["valid"]'''

    def list_required(self):
        '''Returns a set of the required properties for the class'''
        _required_list = set()
        for _prop, _value in self.kds_properties.items():
            if _value.get('kds_requiredByDomain') == self.kds_classUri:
                _required_list.add(_prop)
        try:
            if isinstance(self.primaryKey, list):
                for key in self.primaryKey:
                    _required_list.add(key)
            else:
                _required_list.add(self.primaryKey)
        except:
            pass
        return _required_list

    def list_properties(self):
        '''Returns a set of the properties used for the class'''
        property_list = set()
        for p in self.kds_properties:
            property_list.add(self.kds_properties[p].get('propUri'))
        return property_list

    def list_dependant(self):
        '''Returns a set of properties that are dependent upon the
        creation of another object'''
        _dependent_list = set()
        for _prop in self.kds_properties:
            _range_list = make_list(self.kds_properties[_prop].get('rdfs_range'))
            for _row in _range_list:
                if _row.get('storageType') == "object" or \
                        _row.get('storageType') == "blanknode":
                    _dependent_list.add(_prop)
        _return_obj = []
        for _dep in _dependent_list:
            _range_list = make_list(self.kds_properties[_dep].get('rdfs_range'))
            for _row in _range_list:
                if _row.get('storageType') == "object" or \
                   _row.get('storageType') == "blanknode":
                    _return_obj.append(
                        {"kds_propUri": self.kds_properties[_dep].get("kds_propUri"),
                         "kds_classUri": _row.get("rangeClass")})
        return _return_obj

    def get_property(self, prop_uri):
        '''Method returns the property json object

        keyword Args:
            prop_name: The Name of the property
            prop_uri: The URI of the property
            ** the PropName or URI is required'''
        try:
            return self.kds_properties.get(prop_uri)
        except:
            return None


    def _validate_required_properties(self, rdf_obj, old_data):
        '''Validates whether all required properties have been supplied and
            contain data '''
        debug = True
        _return_error = []
        #create sets for evaluating requiredFields
        _required = self.list_required()
        if debug: print("Required Props: ", _required)
        _data_props = set()
        _deleted_props = set()
        for prop in rdf_obj:
            #remove empty data properties from consideration
            if debug: print(prop,"\n")
            if is_not_null(prop.data) or prop.data != 'None':
                _data_props.add(prop.kds_propUri)
            else:
                _deleted_props.add(prop.kds_propUri)
        # find the properties that already exist in the saved class data
        _old_class_data = self._select_class_query_data(old_data)
        for _prop in _old_class_data:
            # remove empty data properties from consideration
            if is_not_null(_old_class_data[_prop]) or _old_class_data[_prop]\
                    != 'None':
                _data_props.add(_prop)
        # remove the _deleted_props from consideration and add calculated props
        _valid_props = (_data_props - _deleted_props).union( \
                self._get_calculated_properties())
        #Test to see if all the required properties are supplied
        missing_required_properties = _required - _valid_props
        if len(missing_required_properties) > 0:
            _return_error.append({
                "errorType":"missing_required_properties",
                "errorData":{
                    "class":self.kds_classUri,
                    "properties":make_list(missing_required_properties)}})
        if len(_return_error) > 0:
            _return_val = _return_error
        else:
            _return_val = ["valid"]
        return _return_val

    def _get_calculated_properties(self):
        '''lists the properties that will be calculated if no value is
           supplied'''
        _calc_list = set()
        # get the list of processors that will calculate a value for a property
        _value_processors = rdfw().value_processors
        for _prop in self.kds_properties:
            # Any properties that have a default value will be generated at
            # time of save
            if is_not_null(self.kds_properties[_prop].get('kds_defaultVal')):
                _calc_list.add(self.kds_properties[_prop].get('kds_propUri'))
            # get the processors that will run on the property
            _processors = make_list(self.kds_properties[_prop].get(\
                    'kds_propertyProcessing', []))
            # find the processors that will generate a value
            for _processor in _processors:
                #print("processor: ", processor)
                if _processor.get("rdf_type") in _value_processors:
                    _calc_list.add(_prop)
        #any dependant properties will be generated at time of save
        _dependent_list = self.list_dependant()
        # properties that are dependant on another class will assume to be 
        # calculated
        for _prop in _dependent_list:
            _calc_list.add(_prop.get("kds_propUri"))
        return remove_null(_calc_list)

    def _validate_dependant_props(self, rdf_obj, old_data):
        '''Validates that all supplied dependant properties have a uri as an
            object'''
        # dep = self.list_dependant()
        # _return_error = []
        _data_props = set()
        for _prop in rdf_obj:
            #remove empty data properties from consideration
            if is_not_null(_prop.data):
                _data_props.add(_prop.kds_propUri)
        '''for p in dep:
            _data_value = data.get(p)
            if (is_not_null(_data_value)):
                propDetails = self.kds_properties[p]
                r = propDetails.get('range')
                literalOk = false
                for i in r:
                    if i.get('storageType')=='literal':
                        literalOk = True
                if not is_valid_object(_data_value) and not literalOk:
                    _return_error.append({
                        "errorType":"missingDependantObject",
                        "errorData":{
                            "class":self.kds_classUri,
                            "properties":propDetails.get('propUri')}})
        if len(_return_error) > 0:
            return _return_error
        else:'''
        return ["valid"]

    def _validate_property_data(self, rdf_obj, old_data):
        return ["valid"]

    def _validate_security(self, rdf_obj, old_data):
        return ["valid"]

    def _process_class_data(self, rdf_obj):
        '''Reads through the processors in the defination and processes the
            data for saving'''
        debug = False
        _pre_save_data = {}
        _save_data = {}
        _processed_data = {}
        obj = {}
        _required_props = self.list_required()
        _calculated_props = self._get_calculated_properties()
        _old_data = self._select_class_query_data(rdf_obj.query_data) 
        # cycle through the form class data and add old, new, doNotSave and
        # processors for each property
        _class_obj_props = rdf_obj.class_grouping.get(self.kds_classUri,[])
        subject_uri = "<>"
        for prop in _class_obj_props:
            if hasattr(prop, "subject_uri"):
                if prop.subject_uri is not None:
                    subject_uri = prop.subject_uri
                    break
        subject_uri = _old_data.get("!!!!subjectUri", "<>")
        for prop in _class_obj_props:
            _prop_uri = prop.kds_propUri
            if debug:
                if _prop_uri == "schema_image":
                    x=y
            # gather all of the processors for the property
            _class_prop = self.kds_properties.get(_prop_uri,{})
            _class_prop_processors = make_list(_class_prop.get("kds_propertyProcessing"))
            _form_prop_processors = make_list(prop.kds_processors)
            # clean the list of processors by sending a list based on 
            # precedence i.e. the form processors should override the rdf_class
            # processors
            processors = clean_processors([_form_prop_processors,
                                           _class_prop_processors],
                                           self.kds_classUri)
            # remove the property from the list of required properties
            # required properties not in the form will need to be addressed
            _required_prop = False
            if _prop_uri in _required_props:
                _required_props.remove(_prop_uri)
                _required_prop = True
            # remove the property from the list of calculated properties
            # calculated properties not in the form will need to be addressed
            if _prop_uri in _calculated_props:
                _calculated_props.remove(_prop_uri)
            # add the information to the _pre_save_data object
            if not _pre_save_data.get(_prop_uri):
                _pre_save_data[_prop_uri] =\
                        {"new":prop.data,
                         "old":prop.old_data,
                         "classUri": prop.kds_classUri,
                         "required": _required_prop,
                         "editable": prop.editable,
                         "doNotSave": prop.doNotSave,
                         "processors": processors}
            else:
                _temp_list = make_list(_pre_save_data[_prop_uri])
                _temp_list.append(\
                        {"new":prop.data,
                         "old":prop.old_data,
                         "classUri": prop.kds_classUri,
                         "required": _required_prop,
                         "editable": prop.editable,
                         "doNotSave": prop.doNotSave,
                         "processors": processors})
                _pre_save_data[_prop_uri] = _temp_list
        # now deal with missing required properties. cycle through the
        # remaing properties and add them to the _pre_save_data object
        for _prop_uri in _required_props:
            _class_prop = self.kds_properties.get(_prop_uri,{})
            _class_prop_processors = clean_processors([make_list(\
                            _class_prop.get("kds_propertyProcessing"))],
                            self.kds_classUri)
            if _prop_uri == "schema_alternativeName":
                x=1
            # remove the prop from the remaining calculated props
            if _prop_uri in _calculated_props:
                _calculated_props.remove(_prop_uri)
            if not _pre_save_data.get(_prop_uri):
                _pre_save_data[_prop_uri] =\
                        {"new":NotInFormClass(),
                         "old":_old_data.get(_prop_uri),
                         "doNotSave":False,
                         "classUri": self.kds_classUri,
                         "required": True,
                         "editable": True,
                         "processors":_class_prop_processors,
                         "defaultVal":_class_prop.get("kds_defaultVal")}
                if debug: print("psave: ", _pre_save_data[_prop_uri])
            else:
                _temp_list = make_list(_pre_save_data[_prop_uri])
                _pre_save_data[_prop_uri] = _temp_list.append(\
                        {"new":NotInFormClass(),
                         "old":_old_data.get(_prop_uri),
                         "doNotSave": False,
                         "classUri": self.kds_classUri,
                         "editable": True,
                         "processors":_class_prop_processors,
                         "defaultVal":_class_prop.get("kds_defaultVal")})
        
        # now deal with missing calculated properties. cycle through the
        # remaing properties and add them to the _pre_save_data object
        if debug: print("calc props: ", _calculated_props)
        for _prop_uri in _calculated_props:
            if debug: print("########### _calculated_props: ")
            _class_prop = self.kds_properties.get(_prop_uri,{})
            _class_prop_processors = clean_processors([make_list(\
                    _class_prop.get("kds_propertyProcessing"))],
                    self.kds_classUri)
            if not _pre_save_data.get(_prop_uri):
                _pre_save_data[_prop_uri] =\
                        {"new":NotInFormClass(),
                         "old":_old_data.get(_prop_uri),
                         "doNotSave":False,
                         "processors":_class_prop_processors,
                         "defaultVal":_class_prop.get("kds_defaultVal")}
            else:
                _temp_list = make_list(_pre_save_data[_prop_uri])
                _pre_save_data[_prop_uri] =\
                        _temp_list.append(\
                                {"new":NotInFormClass(),
                                 "old":_old_data.get(_prop_uri),
                                 "doNotSave":False,
                                 "processors":_class_prop_processors,
                                 "defaultVal":_class_prop.get("kds_defaultVal")})
        # cycle through the consolidated list of _pre_save_data to
        # test the security, run the processors and calculate any values
        for _prop_uri, prop in _pre_save_data.items():
            # ******* doNotSave property is set during form field creation
            # in get_wtform_field method. It tags fields that are there for
            # validation purposes i.e. password confirm fields ******

            if isinstance(prop, list):
                # a list with in the property occurs when there are
                # multiple fields tied to the property. i.e.
                # password creation or change / imagefield that
                # takes a URL or file
                for _prop_instance in prop:
                    if _prop_instance.get("doNotSave", False):
                        _pre_save_data[_prop_uri].remove(_prop_instance)
                if len(make_list(_pre_save_data[_prop_uri])) == 1:
                    _pre_save_data[_prop_uri] = _pre_save_data[_prop_uri][0]
            # doNotSave = prop.get("doNotSave", False)
        for _prop_uri, _prop in _pre_save_data.items():
            # send each property to be proccessed
            if _prop:
                obj = self._process_prop({"propUri":_prop_uri,
                                          "prop": _prop,
                                          "processedData": _processed_data,
                                          "preSaveData": _pre_save_data})
                _processed_data = obj["processedData"]
                _pre_save_data = obj["preSaveData"]
        if debug: print("PreSaveData----------------")
        if debug: print(json.dumps(dumpable_obj(_pre_save_data), indent=4))
        _save_data = {"data":self.__format_data_for_save(_processed_data,
                                                         _pre_save_data),
                      "subjectUri":subject_uri}
        return _save_data

    def _generate_save_query(self, save_data_obj, subject_uri=None):
        _save_data = save_data_obj.get("data")
        # find the subject_uri positional argument or look in the save_data_obj
        # or return <> as a new node
        if not subject_uri:
            subject_uri = iri(uri(save_data_obj.get('subjectUri', "<>")))
        _save_type = self.kds_storageType
        if subject_uri == "<>" and _save_type.lower() == "blanknode":
            _save_type = "blanknode"
        else:
            _save_type = "object"
        _bn_insert_clause = []
        _insert_clause = ""
        _delete_clause = ""
        _where_clause = ""
        _prop_set = set()
        i = 1
        #print("save data in generateSaveQuery\n",\
                #json.dumps(dumpable_obj(_save_data), indent=4), "\n", _save_data)
        # test to see if there is data to save
        if len(_save_data) > 0:
            for prop in _save_data:
                _prop_set.add(uri(prop[0]))
                _prop_iri = iri(uri(prop[0]))
                if not isinstance(prop[1], DeleteProperty):
                    _obj_val = uri(prop[1])
                    _insert_clause += "{}\n".format(\
                                        make_triple(subject_uri, _prop_iri, _obj_val))
                    _bn_insert_clause.append("\t{} {}".format(_prop_iri, _obj_val))
            if subject_uri != '<>':
                for prop in _prop_set:
                    _prop_iri = iri(uri(prop))
                    _delete_clause += "{}\n".format(\
                                    make_triple(subject_uri, _prop_iri, "?"+str(i)))
                    _where_clause += "OPTIONAL {{ {} }} .\n".format(\
                                    make_triple(subject_uri, _prop_iri, "?"+str(i)))
                    i += 1
            else:
                _obj_val = iri(uri(self.kds_classUri))
                _insert_clause += make_triple(subject_uri, "a", _obj_val) + \
                        "\n"
                _bn_insert_clause.append("\t a {}".format(_obj_val))
            if _save_type == "blanknode":
                _save_query = "[\n{}\n]".format(";\n".join(_bn_insert_clause))
            else:
                if subject_uri != '<>':
                    save_query_template = Template("""{{ prefix }}
                                    DELETE \n{
                                    {{ _delete_clause }} }
                                    INSERT \n{
                                    {{ _insert_clause }} }
                                    WHERE \n{
                                    {{ _where_clause }} }""")
                    _save_query = save_query_template.render(
                        prefix=rdfw().get_prefix(),
                        _delete_clause=_delete_clause,
                        _insert_clause=_insert_clause,
                        _where_clause=_where_clause)
                else:
                    _save_query = "{}\n\n{}".format(
                        rdfw().get_prefix("turtle"),
                        _insert_clause)
            #print(_save_query)
            return {"query":_save_query, "subjectUri":subject_uri}
        else:
            return {"subjectUri":subject_uri}

    def _run_save_query(self, save_query_obj, subject_uri=None):
        _save_query = save_query_obj.get("query")
        if not subject_uri:
            subject_uri = save_query_obj.get("subjectUri")

        if _save_query:
            # a "[" at the start of the save query denotes a blanknode
            # return the blanknode as the query result
            if _save_query[:1] == "[":
                object_value = _save_query
            else:
                # if there is no subject_uri create a new entry in the
                # repository
                if subject_uri == "<>":
                    repository_result = requests.post(
                        fw_config().get("REPOSITORY_URL"),
                        data=_save_query,
        				headers={"Content-type": "text/turtle"})
                    object_value = repository_result.text
                # if the subject uri exists send an update query to the
                # repository
                else:
                    _headers = {"Content-type":"application/sparql-update"}
                    _url = clean_iri(subject_uri)
                    repository_result = requests.patch(_url, data=_save_query,
        				                                     headers=_headers)
                    object_value = iri(subject_uri)
            return {"status": "success",
                    "lastSave": {
                        "objectValue": object_value}
                   }
        else:
            return {"status": "success",
                    "lastSave": {
                        "objectValue": iri(subject_uri),
                        "comment": "No data to Save"}
                   }

    def _process_prop(self, obj):
        # obj = propUri, prop, processedData, _pre_save_data
        # !!!!!!! the merge_prop function will need to be relooked for 
        # instances where we have multiple property entries i.e. a fieldList
        if len(make_list(obj['prop'])) > 1:
            obj = self.__merge_prop(obj)
        processors = obj['prop'].get("processors", [])
        _prop_uri = obj['propUri']
        # process properties that are not in the form
        if isinstance(obj['prop'].get("new"), NotInFormClass):
            # process required properties
            if obj['prop'].get("required"):
                # run all processors: the processor determines how to
                # handle if there is old data
                if len(processors) > 0:
                    for processor in processors.values():
                        obj = run_processor(processor, obj)
                # if the processors did not calculate a value for the
                # property attempt to calculte from the default
                # property settings
                if not obj['prop'].get('calcValue', False):
                    obj_value = calculate_default_value(obj['prop'])
                    obj['processedData'][obj['propUri']] = obj_value
            #else:
                # need to decide if you want to calculate properties
                # that are not required and not in the form
        # if the property is editable process the data
        elif obj['prop'].get("editable"):
            # if the old and new data are different
            #print(obj['prop'].get("new"), " != ", obj['prop'].get("old"))
            if clean_iri(obj['prop'].get("new")) != \
                                    clean_iri(obj['prop'].get("old")):
                #print("true")
                # if the new data is null and the property is not
                # required mark property for deletion
                if not is_not_null(obj['prop'].get("new")) and not \
                                                obj['prop'].get("required"):
                    obj['processedData'][_prop_uri] = DeleteProperty()
                # if the property has new data
                elif is_not_null(obj['prop'].get("new")):
                    if len(processors) > 0:
                        for processor in processors.values():
                            obj = run_processor(processor, obj)
                        if not obj['prop'].get('calcValue', False):
                            obj['processedData'][_prop_uri] = \
                                                       obj['prop'].get("new")
                    else:
                        obj['processedData'][_prop_uri] = obj['prop'].get("new")

        return obj
        
    def __calculate_property(self, obj):
        ''' Reads the obj and calculates a value for the property'''
        return obj

    def __merge_prop(self, obj):
        '''This will need to be expanded to handle more cases right now
        the only case is an image '''
        #_prop_list = obj['prop']
        _keep_image = -1
        
        for i, prop in enumerate(obj['prop']):       
            if isinstance(prop['new'], FileStorage):
                if prop['new'].filename:
                    _keep_image = i
                    break
        for i, prop in enumerate(obj['prop']):
            if i != _keep_image:
                obj['prop'].remove(prop)
        obj['prop'] = obj['prop'][0]
        return obj
        '''_prop_list = obj['prop']
        _class_prop = self.get_property(prop_uri=obj['propUri'])
        propRange = _class_prop.get('''
        '''for prop in _prop_list:
            for name, attribute in prop.items():
                if conflictingValues.get(name):
                    if isinstance(conflictingValues.get(name), list):
                        if not attribute in conflictingValues.get(name):
                            conflictingValues[name].append(attribute)
                    elif conflictingValues.get(name) != attribute:
                        conflictingValues[name] = [conflictingValues[name],
                                                   attribute]
                else:
                    conflictingValues[name] = attribute'''
                    
    def __format_data_for_save(self, processed_data, pre_save_data):
        ''' takes the processed data and formats the values for the sparql
            query '''
        debug = False
        _save_data = []
        #if "obi_recipient" in pre_save_data.keys():
        #    x=y
        if debug: print("format data***********\n")
        if debug: pp.pprint(processed_data)
        # cycle throught the properties in the processed data    
        for _prop_uri, prop in processed_data.items():
            # if the property is maked for deletion add it to the save list
            if isinstance(prop, DeleteProperty):
                _save_data.append([_prop_uri, prop])
            # if the property is a file object send it to the repository and
            # add the new uri to the save data list
            elif isinstance(prop, FileStorage):
                _file_iri = save_file_to_repository(\
                        prop, pre_save_data[_prop_uri][0].get('old'))
                _save_data.append([_prop_uri, _file_iri])
            # otherwise determine the range of the property and format it in 
            # the correct sparl format
            else:
                # some properties have more than one option for the object 
                # value i.e. schema:image can either store a ImageObject or
                # a Url to an image. We need to determine the range options
                _range_list = make_list(self.kds_properties[_prop_uri].get(\
                        "rdfs_range", [{}]))
                _storage_types = set()
                _data_types = set()
                # cycle through the range_list and get the sets of options
                for _range_dict in _range_list:
                    _storage_types.add(_range_dict.get('storageType'))
                    if _range_dict.get('storageType') == "literal":
                        _data_types.add(_range_dict.get('rangeClass'))
                _data_type = "xsd_string"
                for _type in _data_types:
                    if "xsd" in _type:
                        _data_type = _type
                # cycle through the items in the current prop
                _value_list = make_list(prop)
                for item in _value_list:
                    if 'object' in _storage_types or 'blanknode' in \
                            _storage_types:
                        uri_test = uri(item)
                        if debug: print(_prop_uri, " - ", uri_test)
                        if uri_test.startswith("http"):
                            _save_data.append([_prop_uri, iri(uri(item))])
                        elif 'literal' in _storage_types:
                            _save_data.append([_prop_uri, RdfDataType(\
                                    _data_type).sparql(str(item))])
                        else:
                            _save_data.append([_prop_uri, iri(uri(item))])
                    else:
                        _save_data.append([_prop_uri, RdfDataType(\
                                _data_type).sparql(str(item))])
        return _save_data
    
    def _select_class_query_data(self, old_data):
        ''' Find the data in query data that pertains to this class instance
            returns dictionary of data with the subject_uri stored as
            !!!!subject'''

        #print("__________ class queryData:\n", \
        #                        json.dumps(dumpable_obj(old_data), indent=4))
        _old_class_data = {}
        if old_data:
            # find the current class data from the query
            if isinstance(old_data, list):
                for entry in old_data:
                    for _subject_uri, value in entry.items():
                        _class_types = make_list(value.get("rdf_type", []))
                        for _rdf_type in _class_types: 
                            if _rdf_type == self.kds_classUri or \
                                    _rdf_type == "<%s>" % self.kds_classUri:
                                _old_class_data = value
                                _old_class_data["!!!!subjectUri"] = _subject_uri
                                break
            else:    
                for _subject_uri in old_data:
                    _class_types = make_list(old_data[_subject_uri].get( \
                        "rdf_type", []))
                    for _rdf_type in _class_types:
                        if _rdf_type == self.kds_classUri or \
                                    _rdf_type == "<%s>" % self.kds_classUri:
                            _old_class_data = old_data[_subject_uri]
                            _old_class_data["!!!!subjectUri"] = _subject_uri
                        break

        return _old_class_data