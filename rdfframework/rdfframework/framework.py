__author__ = "Mike Stabile, Jeremy Nelson"
import re
import json
import os
import requests
from wtforms import ValidationError
from werkzeug.datastructures import MultiDict
from rdfframework.utilities import fw_config, iri, is_not_null, make_list, \
        remove_null, clean_iri, make_triple, convert_spo_to_dict, DEBUG, \
        render_without_request, code_timer, create_namespace_obj, \
        convert_obj_to_rdf_namespace, pyuri, nouri, uri, pp, \
        JSON_LOCATION   
from rdfframework.processors import clean_processors, run_processor
from rdfframework.sparql import get_data
from .rdfproperty import RdfProperty

class RdfFramework(object):
    ''' base class for Knowledge Links' Graph database RDF vocabulary
        framework'''

    rdf_class_dict = {}       # stores the Triplestore defined class defintions
    class_initialized = False # used to state if the the class was properly
                              #     initialized with RDF definitions
    rdf_form_dict = {}        # stores the Triplestore defined form definitions
    forms_initialized = False # used to state if the form definitions have
                              #     been initialized
    rdf_app_dict = {}         # stors the the Triplestore definged application
                              #     settings
    app_initialized = False   # states if the application has been initialized
    value_processors = []

    def __init__(self):
        reset = False
        if DEBUG:
            print("*** Loading Framework ***")
        self._load_rdf_data(reset)
        self._load_app(reset)
        self._generate_classes(reset)
        self._generate_forms(reset)
        if DEBUG:
            print("*** Framework Loaded ***")

    def user_authentication(self, rdf_obj):
        ''' reads the object for authentication information and sets the
            flask userclass information '''
            
        # find the username and password
        for fld in rdf_obj.rdf_field_list:
            if fld.kds_propUri == "kds_userName":
                _username = fld
            if fld.kds_propUri == "kds_password":
                _password = fld
        # get the stored information
        subject_lookup = _username
        query_data = self.get_obj_data(rdf_obj, 
                                       subject_lookup=_username,
                                       lookup_related=True,
                                       processor_mode="verify")
        if _password.password_verified:
            rdf_obj.save_state = "success"
        else:
            error_msg = "The supplied credentials could not be verified"
            _username.errors.append(" ")
            _password.errors.append(error_msg)
            rdf_obj.save_state = "fail"
            
        

    def form_exists(self, form_path):
        '''Tests to see if the form and instance is valid'''
        if form_path in self.form_list.keys():
            return self.form_list[form_path]
        else:
            return False

    def get_form_path(self, form_uri, instance):
        ''' reads through the list of defined forms and returns the path '''
        for form_path, val in self.form_list.items():
            if val['form_uri'] == form_uri and val['instance_uri'] == instance:
                return form_path
                    
    def get_form_name(self, form_uri):
        '''returns the form name for a form '''
        if form_uri:
            return pyuri(form_uri)
        else:
            return None
            
    def save_object_with_subobj(self, rdf_obj, old_data=None):
        ''' finds the subform field and appends the parent form attributes
           to the subform entries and individually sends the augmented
           subform to the main save_form property'''
        debug = False   
        _parent_fields = []
        _parent_field_list = {}
        result = []
        rdf_obj.save_results = []
        rdf_obj.save_state = "success"
        if debug:
            print("-----------------------")
            for fld in rdf_obj.Recipient.entries[0].form.rdf_field_list:
                print(fld.name, " - ", fld.data, " | ", fld)
            for fld in rdf_obj.Recipient.entries[1].form.rdf_field_list:
                print(fld.name, " - ", fld.data, " | ", fld)
            for fld in rdf_obj.Recipient.entries[2].form.rdf_field_list:
                print(fld.name, " - ", fld.data, " | ", fld)
            print("-----------------------")
        for _field in rdf_obj.rdf_field_list:
            if _field.type != 'FieldList':
                _parent_fields.append(_field)
            else:
                _parent_field_list = rdf_obj.rdf_field_list[:].remove(_field)
        for _field in rdf_obj.rdf_field_list:
            if _field.type == 'FieldList':
                for _entry in _field.entries:
                    #if DEBUG:
                    #    print("__________\n",_entry.__dict__)
                    if _entry.type == 'FormField':
                        if hasattr(_entry.form,"subjectUri"):
                            _entry.form.data_subject_uri = \
                                    _entry.form.subjectUri.data
                            _entry.form.data_class_uri = \
                                    _entry.form.subjectUri.kds_classUri
                            _entry.form.remove_prop(_entry.form.subjectUri)
                            
                            # ------------------------------------------
                            if debug:
                                print("subjectUri: ",_entry.form.subjectUri.data)
                                for fld in _entry.form.rdf_field_list:
                                    print(fld.name, " - ", fld.data, " | ", fld)
                                for fld in _field.entries[2].form.rdf_field_list:
                                    print(fld.name, " - ", fld.data, " | ", fld)
                            # -------------------------------------------
                            
                        _entry.form.add_props(_parent_fields)
                        save_result = self.save_obj(_entry.form, old_data)
                        rdf_obj.save_results.append(save_result)
                        if _entry.form.save_state is not "success":
                            rdf_obj.save_state = "fail"
        rdf_obj.save_subject_uri = rdf_obj.data_subject_uri
        return {"success":True, "results":result} 
            
    def save_obj(self, rdf_obj, old_data=None):
        ''' Recieves RDF_formfactory form, validates and saves the data

         *** Steps ***
         - determine if subform is present
         - group fields by class
         - validate the form data for class requirements
         - determine the class save order. classes with no dependant properties
           saved first
         - send data to classes for processing
         - send data to classes for saving
        '''
        if rdf_obj.is_subobj:
            x=1
        #if old_data is None:
        old_obj_data = self.get_obj_data(rdf_obj) 
        #else:
        #    old_obj_data = old_data
        
        if rdf_obj.has_subobj:
            return self.save_object_with_subobj(rdf_obj, old_obj_data)
        rdf_obj.set_obj_data(query_data=old_obj_data['query_data'])
        #print("~~~~~~~~~ _old_form_data: ", _old_form_data)
        # validate the form data for class requirements (required properties,
        # security, valid data types etc)
        
        _validation = self._validate_obj_by_class_reqs(rdf_obj)
        if not _validation.get('success'):
            rdf_obj.reset_fields()
            print("%%%%%%% validation in save_form", _validation)
            return _validation
        # determine class save order
        _form_by_classes = rdf_obj.class_grouping
        _class_save_order = self._get_save_order(rdf_obj)
        
        if DEBUG: print("xxxxxxxxxxx class save order\n", json.dumps(_class_save_order, indent=4))
        
        _reverse_dependancies = rdf_obj.reverse_dependancies
        _id_class_uri = rdf_obj.data_class_uri
        # save class data
        _data_results = []
        id_value = None
        for _rdf_class in _class_save_order:
            _status = {}
            _status = getattr(self, _rdf_class).save(rdf_obj)
            _data_results.append({"rdfClass":_rdf_class, "status":_status})
            if DEBUG:
                print("status ----------\n", json.dumps(_status))
            if _status.get("status") == "success":
                _update_class = _reverse_dependancies.get(_rdf_class, [])
                if _rdf_class == _id_class_uri:
                    id_value = clean_iri(\
                            _status.get("lastSave", {}).get("objectValue"))
                for _prop in _update_class:
                    found = False
                    for i, field in enumerate(
                            rdf_obj.class_grouping.get(_prop.get('kds_classUri', ''))):
                        if field.kds_propUri ==  _prop.get('kds_propUri'):
                            found = True
                            _form_by_classes[field.kds_classUri][i].data = \
                                _status.get("lastSave", {}).get("objectValue")
                            _form_by_classes[field.kds_classUri][i].editable = \
                                    True
                    if not found:
                        prop_json = getattr(self, _prop.get('kds_classUri')\
                                ).kds_properties.get(_prop.get('kds_propUri'))
                        prop_json['kds_classUri'] = _prop.get('kds_classUri')
                        data = _status.get("lastSave", {}).get("objectValue")
                        new_prop = RdfProperty(prop_json, data)
                                    
                        _form_by_classes[_prop.get('kds_classUri')].append(\
                                new_prop)
        rdf_obj.save_state = "success"                        
        rdf_obj.save_subject_uri = id_value
        rdf_obj.save_results = _data_results
        return  rdf_obj

    def get_prefix(self, format_type="sparql"):
        ''' Generates a string of the rdf namespaces listed used in the
            framework

            formatType: "sparql" or "turtle"
        '''
        _return_str = ""
        for _prefix, _ns in self.ns_obj.items():
            if format_type.lower() == "sparql":
                _return_str += "PREFIX {0}: {1}\n".format(_prefix, iri(_ns))
            elif format_type.lower() == "turtle":
                _return_str += "@prefix {0}: {1} .\n".format(_prefix, iri(_ns))
        return _return_str

    def get_class_links(self, set_of_classes):
        _class_set = set()
        _dependant_classes = set()
        _independant_classes = set()
        _class_dependancies = {}
        _reverse_dependancies = {}
        _class_set = remove_null(_class_set)
        # cycle through all of the rdf classes
        for _rdf_class in set_of_classes:
            # get the instance of the RdfClass
            _current_class = getattr(self, _rdf_class)
            _current_class_dependancies = _current_class.list_dependant()
            # add the dependant properties to the class depenancies dictionay
            _class_dependancies[_rdf_class] = _current_class_dependancies
            for _reverse_class in _current_class_dependancies:
                if not isinstance(_reverse_dependancies.get(_reverse_class.get(\
                        "kds_classUri", "missing")), list):
                    _reverse_dependancies[_reverse_class.get("kds_classUri", \
                            "missing")] = []
                _reverse_dependancies[\
                        _reverse_class.get("kds_classUri", "missing")].append(\
                                {"kds_classUri":_rdf_class,
                                 "kds_propUri":_reverse_class.get("kds_propUri", "")})
            if len(_current_class.list_dependant()) > 0:
                _dependant_classes.add(_current_class.kds_classUri)
            else:
                _independant_classes.add(_current_class.kds_classUri)
        return {"dep_classes": list(_dependant_classes),
                "indep_classes" : list(_independant_classes),
                "dependancies" : _class_dependancies,
                "reverse_dependancies" : _reverse_dependancies}
    
    def get_obj_data(self, rdf_obj, **kwargs):
        ''' returns the data for the current form paramters
        **keyword arguments
        subject_uri: the URI for the subject
        class_uri: the rdf class of the subject
        '''
        debug = False
        _class_uri = kwargs.get("class_uri", rdf_obj.data_class_uri)
        _lookup_class_uri = _class_uri
        subject_uri = kwargs.get("subject_uri", rdf_obj.data_subject_uri)
        _subobj_data = {}
        _data_list = kwargs.get("data_list",False)
        _parent_field = None
        processor_mode = kwargs.get("processor_mode","load")
        # if there is no subject_uri exit the function
        if not is_not_null(subject_uri) and not kwargs.get("subject_lookup"):
            return {'query_data':{}}
        # test to see if a subobj is in the form
        if rdf_obj.has_subobj:
            _sub_rdf_obj = None
            # find the subform field 
            for _field in rdf_obj.rdf_field_list:
                if _field.type == 'FieldList':
                    for _entry in _field.entries:
                        if _entry.type == 'FormField':
                            _sub_rdf_obj = _entry.form
                            _sub_rdf_obj.is_subobj = True
                            _parent_field = _field.name
            # if the subform exists recursively call this method to get the
            # subform data
            if _sub_rdf_obj:
                _subform_data = self.get_obj_data(_sub_rdf_obj,
                                                  subject_uri=subject_uri,
                                                  class_uri=_lookup_class_uri)
        _query_data = convert_spo_to_dict(convert_obj_to_rdf_namespace(\
                    get_data(rdf_obj, **kwargs)))
        rdf_obj.query_data = _query_data
        if debug: pp.pprint(_query_data)
        # compare the return results with the form fields and generate a
        # formData object
        
        _form_data_list = []
        for _item in make_list(_query_data):
            _form_data = {}
            for _prop in rdf_obj.rdf_field_list:
                _prop_uri = _prop.kds_propUri
                _class_uri = _prop.kds_classUri
                _data_value = None
                if "subform" in _prop.kds_fieldType.get("rdf_type",'').lower():
                    for i, _data in enumerate(make_list(\
                            _subform_data.get("form_data"))):
                        for _key, _value in _data.items():
                            _obj_key = "%s-%s-%s" % (_prop.kds_formFieldName,
                                                     i,
                                                    _key)
                            _form_data[_obj_key] = _value 
                else:
                    prop_query_data = None
                    for _subject in _item:
                        if _class_uri in _item[_subject].get("rdf_type"):
                            prop_query_data = _item[_subject].get(_prop_uri)
                            #_prop.query_data = _item[_subject].get(_prop_uri)
                            #_prop.subject_uri = _subject
                            _data_value = _item[_subject].get(_prop_uri)
                    for _processor in _prop.kds_processors:
                            run_processor(_processor, 
                                          rdf_obj, 
                                          _prop, 
                                          processor_mode)
                    if _prop.processed_data is not None:
                        #print(_prop_uri, " __ ", _prop.query_data, "--pro--", _prop.processed_data)
                        #_prop.old_data = _prop.processed_data
                        prop_old_data = _prop.processed_data
                        _prop.processed_data = None
                    else:
                        prop_old_data = prop_query_data
                        #_prop.old_data = _prop.query_data
                        #print(_prop_uri, " __ ", _prop.query_data, "--old--", _prop.old_data)
                    #if _prop.data is None and _prop.old_data is not None:
                    #    _prop.data = _prop.old_data
                    #    _data_value = _prop.data
                    if _data_value is not None:
                        _form_data[_prop.kds_formFieldName] = prop_old_data #_data_value
            _form_data_list.append(MultiDict(_form_data))
        if len(_form_data_list) == 1:
            _form_data_dict = _form_data_list[0]
        elif len(_form_data_list) > 1:
            _form_data_dict = _form_data_list
        else:
            _form_data_dict = MultiDict()
        return {"form_data":_form_data_dict,
                "query_data":_query_data,
                "form_class_uri":_lookup_class_uri}
                    
    def _make_form_list(self):
        ''' creates an indexed dictionary of available forms and attaches
            it to the Framework as form_list attribute'''
        _form_list = {}
        for _form, _details in self.rdf_form_dict.items():
            _form_url = _details.get('kds_formInstructions',{}).get(\
                    "kds_formUrl",nouri(_form)) 
            _instance_list = _details.get('kds_formInstructions',{}).get(\
                    'kds_formInstance',{})    
            for _instance in make_list(_instance_list):
                _instance_url = _instance.get(\
                                "kds_instanceUrl",
                                nouri(_instance.get('kds_formInstanceType','')))
                if _instance_url == "none":
                    _key = _form_url
                else:
                    _key = "{}/{}".format(_form_url, _instance_url)
                _form_list[_key] = {\
                        'form_uri':_form, 
                        'instance_uri':_instance.get('kds_formInstanceType','')}
        self.form_list = _form_list
        
    def _load_app(self, reset):
        ''' queries the rdf definitions and sets the framework attributes
            for the application defaults '''
        if self.app_initialized != True:
            _app_json = self._load_application_defaults(reset)
            self.ns_obj = create_namespace_obj(_app_json)
            self.rdf_app_dict = convert_obj_to_rdf_namespace(_app_json,
                                                             self.ns_obj)
            # add the security attribute
            # add the app attribute
            _key_string = "kds_applicationSecurity"
            for _app_section in self.rdf_app_dict.values():
                try:
                    for _section_key in _app_section.keys():
                        if _section_key == _key_string:
                            self.app_security = _app_section[_section_key]
                            self.app = _app_section
                            break
                except AttributeError:
                    pass
            # add attribute for a list of property processors that
            # will generate a property value when run
            _value_processors = []
            for _processor, value in \
                    self.rdf_app_dict.get("kds_PropertyProcessor", {}).items():
                if value.get("kds_resultType") == "propertyValue":
                    _value_processors.append(_processor)
            self.value_processors = _value_processors
            self.app_initialized = True

    def _generate_classes(self, reset):
        ''' generates a python RdfClass for each defined rdf class in
            the app vocabulary '''
        if self.class_initialized != True:
            _class_json = self._load_rdf_class_defintions(reset)
            self.rdf_class_dict = convert_obj_to_rdf_namespace(_class_json,
                                                               self.ns_obj)
            self.class_initialized = True
            for _rdf_class in self.rdf_class_dict:
                setattr(self,
                        _rdf_class,
                        RdfClass(self.rdf_class_dict[_rdf_class], _rdf_class))

    def _generate_forms(self, reset):
        ''' adds the dictionary of form definitions as an attribute of
            this class. The form python class uses this dictionary to
            create a python form class at the time of calling. '''
        if self.forms_initialized != True:
            _form_json = self._load_rdf_form_defintions(reset)
            self.rdf_form_dict = convert_obj_to_rdf_namespace(_form_json,
                                                              self.ns_obj)
            self._make_form_list()
            self.form_initialized = True

    def _load_application_defaults(self, reset):
        ''' Queries the triplestore for settings defined for the application in
            the kl_app.ttl file'''
        
        if DEBUG:
            print("\tLoading application defaults")
        if reset:
            _sparql = render_without_request(
                "jsonApplicationDefaults.rq",
                graph=fw_config().get('RDF_DEFINITION_GRAPH'))
            _form_list = requests.post(fw_config().get('TRIPLESTORE_URL'),
                                       data={"query": _sparql, 
                                             "format": "json"})
            _string_defs = _form_list.json().get(\
                    'results').get('bindings')[0]['app']['value']
            _json_defs = json.loads(_string_defs)
            with open(
                os.path.join(JSON_LOCATION, "app_query.json"), 
                "w") as file_obj:
                file_obj.write( _string_defs )
        else:
            with open(
                os.path.join(JSON_LOCATION, "app_query.json")) as file_obj:
                _json_defs = json.loads(file_obj.read())
        return _json_defs
            
    def _load_rdf_class_defintions(self, reset):
        ''' Queries the triplestore for list of classes used in the app as
            defined in the kl_app.ttl file'''
        if DEBUG:
            print("\tLoading rdf class definitions")
        if reset:

            _sparql = render_without_request("jsonRdfClassDefinitions.rq",
                                             graph=fw_config().get(\
                                                    'RDF_DEFINITION_GRAPH'))
            _class_list = requests.post(fw_config().get('TRIPLESTORE_URL'),
                                        data={"query": _sparql, "format": "json"})
            _string_defs = _class_list.json().get(\
                    'results').get('bindings')[0]['appClasses']['value']
            _json_defs = json.loads(_string_defs)
            with open(
                os.path.join(JSON_LOCATION,"class_query.json"), 
                "w") as file_obj:
                file_obj.write( _string_defs )
        else:
            with open(
                os.path.join(JSON_LOCATION, "class_query.json")) as file_obj:
                _json_defs = json.loads(file_obj.read())
        return _json_defs

    def _load_rdf_form_defintions(self, reset):
        ''' Queries the triplestore for list of forms used in the app as
            defined in the kl_app.ttl file'''
        if DEBUG:
            print("\tLoading form definitions")
        if reset:
            _sparql = render_without_request("jsonFormQueryTemplate.rq",
                                             graph=fw_config().get(\
                                                    'RDF_DEFINITION_GRAPH'))
            _form_list = requests.post(fw_config().get('TRIPLESTORE_URL'),
                                       data={"query": _sparql, "format": "json"})
            _raw_json = _form_list.json().get('results').get('bindings'\
                    )[0]['appForms']['value']
            _string_defs = _raw_json.replace('hasProperty":', 'properties":')
            _json_defs = json.loads(_string_defs)
            with open(
                os.path.join(JSON_LOCATION, "form_query.json"),
                "w") as file_obj:
                file_obj.write( _string_defs)
        else:
            with open(
                os.path.join(JSON_LOCATION, "form_query.json")) as file_obj:
                _json_defs = json.loads(file_obj.read())
        return _json_defs

    def _validate_obj_by_class_reqs(self, rdf_obj):
        '''This method will cycle thhrought the objects rdf classes and
           call the classes validate_form_data method and return the results'''

        _validation_results = {}
        _validation_errors = []
        for _rdf_class in rdf_obj.class_grouping:
            _current_class = getattr(self, _rdf_class)
            _validation_results = _current_class.validate_obj_data(\
                    rdf_obj.class_grouping[_rdf_class], rdf_obj.query_data)
            if not _validation_results.get("success", True):
                _validation_errors += _validation_results.get("errors", [])
        if len(_validation_errors) > 0:
            for _error in _validation_errors:
                for _prop in make_list(_error.get("errorData", {}).get(\
                        "kds_propUri", [])):
                    _obj_prop = getattr(rdf_obj, _prop.kds_propUri)
                    if hasattr(_obj_prop, "errors"):
                        _prop.errors.append(_error.get(\
                                "formErrorMessage"))
                    else:
                        setattr(_obj_prop, "errors", [_error.get(\
                                "formErrorMessage")])
            return {"success": False, "obj":rdf_obj, "errors": \
                        _validation_errors}
        else:
            return {"success": True}

    def _get_save_order(self, rdf_obj):
        '''Cycle through the classes and determine in what order they need
           to be saved
           1. Classes who's properties don't rely on another class
           2. Classes that that depend on classes in step 1
           3. Classes stored as blanknodes of Step 2 '''

        _save_order = []
        _save_last = []
        for _rdf_class in rdf_obj.indep_classes:
            _save_order.append(_rdf_class)
        for _rdf_class in rdf_obj.dep_classes:
            _dependant = True
            for _dep_class in rdf_obj.dependancies:
                if _dep_class != _rdf_class:
                    for _prop in rdf_obj.dependancies.get(_dep_class, []):
                        #print(_class_name, " d:", _dep_class, " r:", _rdf_class, " p:",
                              #_prop.get('classUri'))
                        if _prop.get('kds_classUri') == _rdf_class:
                            _dependant = False
            if not _dependant:
                _save_order.append(_rdf_class)
            else:
                _save_last.append(_rdf_class)
        return _save_order + _save_last
    
    def _load_rdf_data(self, reset=False):
        ''' loads the RDF/turtle application data to the triplestore '''
        if reset:
            base_url = fw_config().get('ORGANIZATION').get('url')
            triplestore_url = fw_config().get('TRIPLESTORE_URL')
            # Strip off trailing forward slash for TTL template
            if base_url.endswith("/"):
                base_url = base_url[:-1]
            # if the extensions exist in the triplestore drop the graph
            stmt = "DROP GRAPH <http://knowledgelinks.io/ns/application-framework/>;"
            drop_extensions = requests.post(
                url=triplestore_url,
                params={"update": stmt})
            # render the extensions with the base URL
            # must use a ***NON FLASK*** routing since flask is not completely
            # initiated
            rdf_resource_templates = [
                "kds-app.ttl",
                "kds-vocab.ttl",
                "kds-resources.ttl"]
            rdf_data = []
            for template in rdf_resource_templates:
                rdf_data.append(
                    render_without_request(
                        template,
                        base_url=base_url))
            # load the extensions in the triplestore
            context_uri = "http://knowledgelinks.io/ns/application-framework/" 
            for data in rdf_data:
                result = requests.post(
                    url=triplestore_url,
                    headers={"Content-Type": "text/turtle"},
                    params={"context-uri": context_uri},
                    data=data)
                if result.status_code > 399:
                    raise ValueError("Cannot load extensions in {}".format(
                        triplestore_url))  
                      
    # possible deletion: no longer in use. Commented out till certian                
    """def get_form_data(self, rdf_form, **kwargs):
        ''' returns the data for the current form paramters

        **keyword arguments
        subject_uri: the URI for the subject
        class_uri: the rdf class of the subject
        '''
        _class_uri = kwargs.get("class_uri", rdf_form.data_class_uri)
        _lookup_class_uri = _class_uri
        #if hasattr(rdf_form,"subjectUri"):
        #    subject_uri = rdf_form.subjectUri.data
        #else:
        subject_uri = kwargs.get("subject_uri", rdf_form.data_subject_uri)
        _subform_data = {}
        _data_list = kwargs.get("data_list",False)
        _parent_field = None
        # test to see if a subform is in the form
        if rdf_form.has_subform:
            _sub_rdf_form = None
            # find the subform field 
            for _field in rdf_form:
            #print(_field.__dict__,"\n********************\n")
                if _field.type == 'FieldList':
                    for _entry in _field.entries:
                        print("__________\n",_entry.__dict__)
                        if _entry.type == 'FormField':
                            _sub_rdf_form = _entry.form
                            _parent_field = _field.name
            # if the subform exists recursively call this method to get the
            # subform data
            if _sub_rdf_form:
                _subform_data = self.get_form_data(_sub_rdf_form,
                                                   subject_uri=subject_uri,
                                                   class_uri=_lookup_class_uri,
                                                   data_list=True)
        if DEBUG:      
            print("tttttt subform data\n",json.dumps(_subform_data, indent=4))

        _class_name = self.get_class_name(_class_uri)

        subject_uri = kwargs.get("subject_uri", rdf_form.data_subject_uri)
        #print("%%%%%%%%%%% subject_uri: ",subject_uri)
        _sparql_args = None
        _class_links = self.get_form_class_links(rdf_form)
        _sparql_constructor = dict.copy(_class_links['dependancies'])
        if DEBUG:
            print("+++++++++++++++++++++++ Dependancies:\n", json.dumps(_sparql_constructor, indent=4))
        _base_subject_finder = None
        _linked_class = None
        _linked_prop = False
        _sparql_elements = []
        if is_not_null(subject_uri):
            # find the primary linkage between the supplied subjectId and
            # other form classes
            for _rdf_class in _sparql_constructor:
                for _prop in _sparql_constructor[_rdf_class]:
                    try:
                        if _class_uri == _prop.get("classUri"):
                            _sparql_args = _prop
                            _linked_class = _rdf_class
                            _sparql_constructor[_rdf_class].remove(_prop)
                            if _rdf_class != _lookup_class_uri:
                                _linked_prop = True

                    except:
                        pass
            # generate the triple pattern for linked class
            if DEBUG:
                print("+++++++++++++++++++++++ SPARQL Constructor:\n", json.dumps(_sparql_constructor, indent=4))
            if _sparql_args:
                # create a binding for multi-item results
                if _data_list:
                    _list_binding = "BIND(?classID AS ?itemID) ."
                else:
                    _list_binding = ''
                _base_subject_finder = \
                        "BIND({} AS ?baseSub) .\n\t{}\n\t{}\n\t{}".format(
                            iri(subject_uri),
                            make_triple("?baseSub",
                                        "a",
                                        iri(_lookup_class_uri)),
                            make_triple("?classID",
                                        iri(_sparql_args.get("propUri")),
                                        "?baseSub"),
                            _list_binding)
               #print("base subject Finder:\n", _base_subject_finder)
                if _linked_prop:
                    if _data_list:
                        _list_binding = "BIND(?s AS ?itemID) ."
                    else:
                        _list_binding = ''
                    _sparql_elements.append(\
                            "BIND({} AS ?baseSub) .\n\t{}\n\t{}\n\t{}\n\t?s ?p ?o .".format(\
                                    iri(subject_uri),
                                    make_triple("?baseSub",
                                                "a",
                                                iri(_lookup_class_uri)),
                                    make_triple("?s",
                                                iri(_sparql_args.get("propUri")),
                                                "?baseSub"),
                                    _list_binding))
            # iterrate though the classes used in the form and generate the
            # spaqrl triples to pull the data for that class
            for _rdf_class in _sparql_constructor:
                if _rdf_class == _class_name:
                    if _data_list:
                        _list_binding = "BIND(?s AS ?itemID) ."
                    else:
                        _list_binding = ''
                    _sparql_elements.append(\
                            "\tBIND({} AS ?s) .\n\t{}\n\t{}\n\t?s ?p ?o .".format(
                                iri(subject_uri),
                                make_triple("?s", "a", iri(_lookup_class_uri)),
                                _list_binding))
                for _prop in _sparql_constructor[_rdf_class]:
                    if _rdf_class == _class_name:
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
                                            iri(_lookup_class_uri)),
                                make_triple("?baseSub",
                                            iri(_prop.get("propUri")),
                                            "?s"),
                                _list_binding)
                        _sparql_elements.append(_sparql_arg)
                    elif _rdf_class == _linked_class:
                        _sparql_elements.append(
                            "\t{}\n\t{}\n\t?s ?p ?o .".format(
                                _base_subject_finder,
                                make_triple("?classID",
                                            iri(_prop.get("propUri")),
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
                                             prefix=self.get_prefix(),
                                             query=_sparql_unions,
                                             list_binding=_list_binding)
            if DEBUG:
                print(_sparql)
            # query the triplestore
            code_timer().log("loadOldData", "pre send query")
            _form_data_query =\
                    requests.post(fw_config().get('TRIPLESTORE_URL'),
                                  data={"query": _sparql, "format": "json"})
            code_timer().log("loadOldData", "post send query")
            #print(json.dumps(_form_data_query.json().get('results').get(\
                    #'bindings'), indent=4))
            _query_data = convert_spo_to_dict(\
                    _form_data_query.json().get('results').get('bindings'))
            code_timer().log("loadOldData", "post convert query")
            #print("form query data _____\n", json.dumps(_query_data, indent=4))
            #_query_data = _form_data_query.json().get('results').get('bindings')
            #_query_data = json.loads(_form_data_query.json().get('results').get(
            #'bindings')[0]['itemJson']['value'])
        else:
            _query_data = {}
        # compare the return results with the form fields and generate a
        # formData object
        
        _form_data_list = []
        for _item in make_list(_query_data):
            _form_data = {}
            for _row in rdf_form.rdfFieldList:
                for _prop in _row:
                    #print(_prop, "\n\n")
                    _prop_uri = _prop.get("propUri")
                    _class_uri = _prop.get("classUri")
                    #print(_class_uri, " ", _prop_uri, "\n\n")
                    _data_value = None
                    if "subform" in _prop.get("fieldType",{}).get("type",'').lower():
                        for i, _data in enumerate(_subform_data.get("formdata")):
                            for _key, _value in _data.items():
                                _form_data["%s-%s-%s" % (_prop.get("formFieldName"),i,_key)] = _value   
                    else:
                        for _subject in _item:
                            if _class_uri in _item[_subject].get( \
                                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"):
                                _data_value = _item[_subject].get(_prop.get("propUri"))
                        if _data_value:
                            _processors = clean_processors(
                                            make_list(_prop.get("processors")), _class_uri)
                            #print("processors - ", _prop_uri, " - ", _processors,
                                  #"\npre - ", make_list(_prop.get("processors")))
                            _processors = remove_null(_processors)
                            for _processor in _processors:
                                _data_value = \
                                        run_processor(_processor,
                                                      {"propUri": _prop_uri,
                                                       "classUri": _class_uri,
                                                       "prop": _prop,
                                                       "queryData": _item,
                                                       "dataValue": _data_value},
                                                      "load")
                        if _data_value is not None:
                            _form_data[_prop.get("formFieldName")] = _data_value
            _form_data_list.append(MultiDict(_form_data))
        if len(_form_data_list) == 1:
            _form_data_dict = _form_data_list[0]
        elif len(_form_data_list) > 1:
            _form_data_dict = _form_data_list
        else:
            _form_data_dict = MultiDict()
        code_timer().log("loadOldData", "post load into MultiDict")
        #print("data:\n", _form_data)
        #print("dataDict:\n", _form_data_dict)
        code_timer().print_timer("loadOldData", delete=True)
        return {"formdata":_form_data_dict,
                "queryData":_query_data,
                "formClassUri":_lookup_class_uri}"""
    
    # possible deletion: no longer in use. Commented out till certian
    '''def _find_form_field_name(self, rdf_form, prop_uri):
        for _row in rdf_form.rdfFieldList:
            for _prop in _row:
                if _prop.get("propUri") == prop_uri:
                    return _prop.get("formFieldName")
        return None'''
        
    # possible deletion: no longer in use. Commented out till certian
    """def get_class_name(self, class_uri):
        '''This method returns the rdf class name for the supplied Class URI'''
        for _rdf_class in self.rdf_class_dict:
            _current_class_uri = self.rdf_class_dict.get(_rdf_class, {}).get(\
                    "classUri")
            if _current_class_uri == class_uri:
                return _rdf_class
        return ''"""
        
    # possible deletion: no longer in use. Commented out till certian
    """def get_property(self, **kwargs):
        ''' Method returns a list of the property json objects where the
            property is used

        keyword Args:
            class_name: *Optional the name of Class
            class_uri: *Optional the Uri of the Class
            prop_name: The Name of the property
            prop_uri: The URI of the property
            ** the Prop Name or URI is required'''
        _return_list = []
        _class_name = kwargs.get("class_name")
        _class_uri = kwargs.get("class_uri")
        _prop_name = kwargs.get("prop_name")
        _prop_uri = kwargs.get("prop_uri")
        if _class_name or _class_uri:
            if _class_uri:
                _class_name = self.get_class_name(_class_uri)
            if _prop_uri:
                _return_list.append(getattr(self, _class_name).get_property(\
                        prop_uri=_prop_uri))
            else:
                _return_list.append(getattr(self, _class_name).get_property(\
                        prop_name=_prop_name))
        else:
            for _rdf_class in self.rdf_class_dict:
                if _prop_name:
                    _current__class_prop = getattr(self, _rdf_class).get_property(\
                            prop_name=_prop_name)
                else:
                    _current__class_prop = getattr(self, _rdf_class).get_property(\
                            prop_uri=_prop_uri)
                if _current__class_prop:
                    _return_list.append(_current__class_prop)
        return _return_list"""
    
    # possible deletion: no longer in use. Commented out till certian    
    """def _remove_field_from_json(self, rdf_field_json, field_name):
        ''' removes a field form the rdfFieldList form attribute '''
        for _row in rdf_field_json:
            for _field in _row:
                if _field.get('formFieldName') == field_name:
                    _row.remove(_field)
        return rdf_field_json"""

# Theses imports are placed at the end of the module to avoid circular imports
from rdfframework import RdfClass
#from rdfframework import RdfDataType
