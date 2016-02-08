__author__ = "Mike Stabile, Jeremy Nelson"
import re
import json
import requests
from werkzeug.datastructures import MultiDict
from rdfframework.utilities import fw_config, iri, is_not_null, make_list, \
        remove_null, clean_iri, make_triple, convert_spo_to_dict, DEBUG, \
        render_without_request, code_timer
from rdfframework.processors import clean_processors, run_processor


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
        if DEBUG:
            print("*** Loading Framework ***")
        self._load_app()
        self._generate_classes()
        self._generate_forms()
        if DEBUG:
            print("*** Framework Loaded ***")


    def get_class_name(self, class_uri):
        '''This method returns the rdf class name for the supplied Class URI'''
        for _rdf_class in self.rdf_class_dict:
            _current_class_uri = self.rdf_class_dict.get(_rdf_class, {}).get(\
                    "classUri")
            if _current_class_uri == class_uri:
                return _rdf_class
        return ''

    def get_property(self, **kwargs):
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
        return _return_list

    def form_exists(self, form_name, form_instance):
        '''Tests to see if the form and instance is valid'''

        if not form_name in self.rdf_form_dict:
            return False
        instances = make_list(self.rdf_form_dict[form_name]['formInstructions'\
                ].get('formInstance', []))
        for instance in instances:
            if "http://knowledgelinks.io/ns/data-resources/{}".format(\
                    form_instance) == instance.get('formInstanceType'):
                return True
        return False

    def get_form_name(self, form_uri):
        '''returns the form name for a form

        rightnow this is a simple regex but is in place if a more
        complicated search method needs to be used in the future'''
        if form_uri:
            return re.sub(r"^(.*[#/])", "", form_uri)
        else:
            return None
    
    def _remove_field_from_json(self, rdf_field_json, field_name):
        ''' removes a field form the rdfFieldList form attribute '''
        for _row in rdf_field_json:
            for _field in _row:
                if _field.get('formFieldName') == field_name:
                    _row.remove(_field)
        return rdf_field_json
        
    def save_form_with_subform(self, rdf_form):
        ''' finds the subform field and appends the parent form attributes
           to the subform entries and individually sends the augmented
           subform to the main save_form property'''
           
        _parent_fields = []
        _parent_field_list = {}
        result = []
        for _field in rdf_form:
            if _field.type != 'FieldList':
                _parent_fields.append(_field)
            else:
                _parent_field_list = self._remove_field_from_json(\
                        rdf_form.rdfFieldList, _field.name)
        for _field in rdf_form:
            if _field.type == 'FieldList':
                for _entry in _field.entries:
                    if DEBUG:
                        print("__________\n",_entry.__dict__)
                    if _entry.type == 'FormField':
                        for _parent_field in _parent_fields:
                            setattr(_entry.form,_parent_field.name,_parent_field)
                            _entry.form._fields.update(\
                                    {_parent_field.name:_parent_field})
                        _entry.form.rdfFieldList = _entry.form.rdfFieldList + \
                                 _parent_field_list
                        if hasattr(_entry.form,"subjectUri"):
                            _entry.form.dataSubjectUri = \
                                    _entry.form.subjectUri.data
                            del _entry.form.subjectUri
                            for _row in _entry.form.rdfFieldList:
                                for _fld in _row:
                                    if _fld['propUri'] == 'subjectUri':
                                        _row.remove(_fld)
                        result.append(self.save_form(_entry.form))
        return {"success":True, "results":result} 
            
    def save_form(self, rdf_form):
        '''Recieves RDF_formfactory form, validates and saves the data

         *** Steps ***
         - determine if subform is present
         - group fields by class
         - validate the form data for class requirements
         - determine the class save order. classes with no dependant properties
           saved first
         - send data to classes for processing
         - send data to classes for saving
         '''
         
        if rdf_form.has_subform:
            return self.save_form_with_subform(rdf_form)
        # group fields by class
        _form_by_classes = self._organize_form_by_classes(rdf_form)

        # get data of edited objects
        _old_form_data = self.get_form_data(rdf_form)
        _id_class_uri = _old_form_data.get("formClassUri")
        #print("~~~~~~~~~ _old_form_data: ", _old_form_data)
        # validate the form data for class requirements (required properties,
        # security, valid data types etc)
        _validation = self._validate_form_by_class_reqs(\
                _form_by_classes, rdf_form, _old_form_data)
        if not _validation.get('success'):
            #print("%%%%%%% validation in save_form", _validation)
            return _validation
        # determine class save order
        #print("^^^^^^^^^^^^^^^ Passed Validation")

        _class_save_order = self._get_save_order(rdf_form)
        if DEBUG:
            print("xxxxxxxxxxx class save order\n", json.dumps(_class_save_order, indent=4))
        _reverse_dependancies = _class_save_order.get("reverseDependancies", {})
        _class_save_order = _class_save_order.get("saveOrder", {})

        # save class data
        _data_results = []
        id_value = None
        for _rdf_class in _class_save_order:
            _status = {}
            _class_name = self.get_class_name(_rdf_class)
            _status = getattr(self, _class_name).save(_form_by_classes.get(\
                    _class_name, []), _old_form_data)
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
                            _form_by_classes.get(_prop.get('className', ''))):
                        if field.get('fieldJson', {}).get('propUri') ==\
                           _prop.get('propUri', ''):
                            found = True
                            class_name = _prop.get('className', '')
                            _form_by_classes[class_name][i]['data'] = \
                                _status.get("lastSave", {}).get("objectValue")
                    if not found:
                        _form_by_classes[_prop.get('className', '')].append({
                            'data': _status.get("lastSave", {}).get(\
                                        "objectValue"),
                            'fieldJson': self.get_property(
                                class_name=_prop.get("className"),
                                prop_name=_prop.get("propName"))[0]})
        return  {"success":True, "classLinks":_class_save_order, "oldFormData":\
                    _old_form_data, "dataResults":_data_results, "idValue": id_value}

    def get_prefix(self, format_type="sparql"):
        ''' Generates a string of the rdf namespaces listed used in the
            framework

            formatType: "sparql" or "turtle"
        '''
        _return_str = ""
        for _ns in self.rdf_app_dict['application'].get("appNameSpace", []):
            if format_type.lower() == "sparql":
                _return_str += "PREFIX {0}: {1}\n".format(_ns.get('prefix'),
                                                          iri(_ns.get(\
                                                          'nameSpaceUri')))
            elif format_type.lower() == "turtle":
                _return_str += "@prefix {0}: {1} .\n".format(
                    _ns.get('prefix'), iri(_ns.get('nameSpaceUri')))
        return _return_str

    def _load_app(self):
        if self.app_initialized != True:
            _app_json = self._load_application_defaults()
            self.rdf_app_dict = _app_json
            # add attribute for a list of property processors that
            # will generate a property value when run
            _value_processors = []
            for _processor, value in \
                    _app_json.get("PropertyProcessor", {}).items():
                if value.get("resultType") == "propertyValue":
                    _value_processors.append(\
                        "http://knowledgelinks.io/ns/data-resources/%s" % \
                            (_processor))
            self.value_processors = _value_processors
            self.app_initialized = True

    def _generate_classes(self):
        ''' generates a python RdfClass for each defined rdf class in
            the app vocabulary '''
        if self.class_initialized != True:
            _class_json = self._load_rdf_class_defintions()
            self.rdf_class_dict = _class_json
            self.class_initialized = True
            for _rdf_class in self.rdf_class_dict:
                setattr(self,
                        _rdf_class,
                        RdfClass(_class_json[_rdf_class], _rdf_class))

    def _generate_forms(self):
        ''' adds the dictionary of form definitions as an attribute of
            this class. The form python class uses this dictionary to
            create a python form class at the time of calling. '''
        if self.forms_initialized != True:
            _form_json = self._load_rdf_form_defintions()
            self.rdf_form_dict = _form_json
            self.form_initialized = True

    def _load_application_defaults(self):
        ''' Queries the triplestore for settings defined for the application in
            the kl_app.ttl file'''
        if DEBUG:
            print("\tLoading application defaults")
        _sparql = render_without_request(
            "jsonApplicationDefaults.rq",
            graph=fw_config().get('RDF_DEFINITION_GRAPH'))
        _form_list = requests.post(fw_config().get('TRIPLESTORE_URL'),
                                   data={"query": _sparql, "format": "json"})
        return json.loads(_form_list.json().get('results').get('bindings'\
                )[0]['app']['value'])

    def _load_rdf_class_defintions(self):
        ''' Queries the triplestore for list of classes used in the app as
            defined in the kl_app.ttl file'''
        if DEBUG:
            print("\tLoading rdf class definitions")
        _sparql = render_without_request("jsonRdfClassDefinitions.rq",
                                         graph=fw_config().get(\
                                                'RDF_DEFINITION_GRAPH'))
        _class_list = requests.post(fw_config().get('TRIPLESTORE_URL'),
                                    data={"query": _sparql, "format": "json"})
        return json.loads(_class_list.json().get('results').get('bindings'\
                )[0]['appClasses']['value'])

    def _load_rdf_form_defintions(self):
        ''' Queries the triplestore for list of forms used in the app as
            defined in the kl_app.ttl file'''
        if DEBUG:
            print("\tLoading form definitions")
        _sparql = render_without_request("jsonFormQueryTemplate.rq",
                                         graph=fw_config().get(\
                                                'RDF_DEFINITION_GRAPH'))
        _form_list = requests.post(fw_config().get('TRIPLESTORE_URL'),
                                   data={"query": _sparql, "format": "json"})
        _raw_json = _form_list.json().get('results').get('bindings'\
                )[0]['appForms']['value']
        return json.loads(_raw_json.replace('"hasProperty":', '"properties":'))

    def _organize_form_by_classes(self, rdf_form):
        ''' Arrange the form objects and data by rdf class for validation and
            saveing'''
        _return_obj = {}
        for _row in rdf_form.rdfFieldList:
            for _field in _row:
                _append_obj = {"fieldJson":_field, "data":getattr(rdf_form, \
                            _field.get("formFieldName")).data}
                            #, "wtfield":getattr(rdf_form, \
                            #_field.get("formFieldName"))}
                try:
                    _return_obj[_field.get('className')].append(_append_obj)
                except:
                    _return_obj[_field.get('className')] = []
                    _return_obj[_field.get('className')].append(_append_obj)
        return _return_obj

    def get_form_class_links(self, rdf_form):
        '''get linkages between the classes in the form'''
        _return_obj = {}
        _class_set = set()
        # get all of the unique rdf classes in the passed in form
        for _row in rdf_form.rdfFieldList:
            for _field in _row:
                _class_set.add(_field.get('className'))
        _dependant_classes = set()
        _independant_classes = set()
        _class_dependancies = {}
        _reverse_dependancies = {}
        _class_set = remove_null(_class_set)
        # cycle through all of the rdf classes
        for _rdf_class in _class_set:
            # get the instance of the RdfClass
            _current_class = getattr(self, _rdf_class)
            _current_class_dependancies = _current_class.list_dependant()
            # add the dependant properties to the class depenancies dictionay
            _class_dependancies[_rdf_class] = _current_class_dependancies
            for _reverse_class in _current_class_dependancies:
                if not isinstance(_reverse_dependancies.get(_reverse_class.get(\
                        "classUri", "missing")), list):
                    _reverse_dependancies[_reverse_class.get("classUri", \
                            "missing")] = []
                _reverse_dependancies[\
                        _reverse_class.get("classUri", "missing")].append(\
                                {"className":_rdf_class,
                                 "propName":_reverse_class.get("propName", ""),
                                 "propUri":_reverse_class.get("propUri", "")})
            if len(_current_class.list_dependant()) > 0:
                _dependant_classes.add(_current_class.classUri)
            else:
                _independant_classes.add(_current_class.classUri)
        _return_obj = {"depClasses": list(_dependant_classes),
                       "indepClasses": list(_independant_classes),
                       "dependancies": _class_dependancies,
                       "reverseDependancies": _reverse_dependancies}
        return _return_obj

    def _validate_form_by_class_reqs(self,
                                     form_by_classes,
                                     rdf_form,
                                     old_form_data):
        '''This method will cycle thhrought the form classes and
           call the classes validate_form_data method and return the results'''

        _validation_results = {}
        _validation_errors = []
        for _rdf_class in form_by_classes:
            _current_class = getattr(self, _rdf_class)
            _validation_results = _current_class.validate_form_data(\
                    form_by_classes[_rdf_class], old_form_data)
            if not _validation_results.get("success", True):
                _validation_errors += _validation_results.get("errors", [])
        if len(_validation_errors) > 0:
            for _error in _validation_errors:
                for _prop in make_list(_error.get("errorData", {}).get(\
                        "propUri", [])):
                    _form_field_name = self._find_form_field_name(rdf_form,
                                                                  _prop)
                    if _form_field_name:
                        _form_prop = getattr(rdf_form, _form_field_name)
                        if hasattr(_form_prop, "errors"):
                            _form_prop.errors.append(_error.get(\
                                    "formErrorMessage"))
                        else:
                            setattr(_form_prop, "errors", [_error.get(\
                                    "formErrorMessage")])


            return {"success": False, "form":rdf_form, "errors": \
                        _validation_errors}
        else:
            return {"success": True}

    def _find_form_field_name(self, rdf_form, prop_uri):
        for _row in rdf_form.rdfFieldList:
            for _prop in _row:
                if _prop.get("propUri") == prop_uri:
                    return _prop.get("formFieldName")
        return None

    def get_form_data(self, rdf_form, **kwargs):
        ''' returns the data for the current form paramters

        **keyword arguments
        subject_uri: the URI for the subject
        class_uri: the rdf class of the subject
        '''
        _class_uri = kwargs.get("class_uri", rdf_form.dataClassUri)
        _lookup_class_uri = _class_uri
        #if hasattr(rdf_form,"subjectUri"):
        #    subject_uri = rdf_form.subjectUri.data
        #else:
        subject_uri = kwargs.get("subject_uri", rdf_form.dataSubjectUri)
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

        subject_uri = kwargs.get("subject_uri", rdf_form.dataSubjectUri)
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
                "formClassUri":_lookup_class_uri}

    def _get_save_order(self, rdf_form):
        '''Cycle through the classes and determine in what order they need
           to be saved
           1. Classes who's properties don't rely on another class
           2. Classes that that depend on classes in step 1
           3. Classes stored as blanknodes of Step 2 '''
        _class_links = self.get_form_class_links(rdf_form)
        #print(json.dumps(_class_links, indent=4))
        _save_order = []
        _save_last = []
        for _rdf_class in _class_links.get("indepClasses", []):
            _save_order.append(_rdf_class)
        for _rdf_class in _class_links.get("depClasses", []):
            _dependant = True
            _class_name = self.get_class_name(_rdf_class)
            for _dep_class in _class_links.get("dependancies", {}):
                if _dep_class != _class_name:
                    for _prop in _class_links.get("dependancies", {}\
                            ).get(_dep_class, []):
                        #print(_class_name, " d:", _dep_class, " r:", _rdf_class, " p:",
                              #_prop.get('classUri'))
                        if _prop.get('classUri') == _rdf_class:
                            _dependant = False
            if not _dependant:
                _save_order.append(_rdf_class)
            else:
                _save_last.append(_rdf_class)
        return {"saveOrder":_save_order + _save_last,
                "reverseDependancies":_class_links.get("reverseDependancies", {})}

# Theses imports are placed at the end of the module to avoid circular imports
from rdfframework import RdfClass
from rdfframework import RdfDataType
