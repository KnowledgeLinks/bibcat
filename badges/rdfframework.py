"""Module for RDF forms managment"""

import os
import re
from base64 import b64encode
import datetime
import requests
from flask import current_app, json
from jinja2 import Template
from rdflib import Namespace, RDF, RDFS, OWL, XSD
from werkzeug.datastructures import FileStorage, MultiDict
from passlib.hash import sha256_crypt
from dateutil.parser import parse
try:
    from flask_wtf import Form
    from flask_wtf.file import FileField
except ImportError:
    from wtforms import Form
from wtforms.fields import StringField, TextAreaField, PasswordField, \
        BooleanField, FileField, DateField, DateTimeField, SelectField, Field,\
        FormField, FieldList
from wtforms.validators import Length, URL, Email, EqualTo, NumberRange, \
        Required, Regexp, InputRequired, Optional
from wtforms.widgets import TextInput, html_params, HTMLString
from wtforms.compat import text_type, iteritems
from wtforms import ValidationError
from .utilities import render_without_request
from .codetimer import code_timer
from .debugutilities import dumpable_obj

__author__ = "Mike Stabile, Jeremy Nelson"

DC = Namespace("http://purl.org/dc/elements/1.1/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
DOAP = Namespace("http://usefulinc.com/ns/doap#")
FOAF = Namespace("http://xmlns.com/foaf/spec/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
RDF_GLOBAL = None
FRAMEWORK_CONFIG = None

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
        print("*** Loading Framework ***")
        self._load_app()
        self._generate_classes()
        self._generate_forms()
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
            #print(_field.__dict__,"\n********************\n")
            if _field.type == 'FieldList':
                for _entry in _field.entries:
                    print("__________\n",_entry.__dict__)
                    if _entry.type == 'FormField':
                        #print("---------\n",_entry.form.__dict__)
                        for _parent_field in _parent_fields:
                            setattr(_entry.form,_parent_field.name,_parent_field)
                            _entry.form._fields.update({_parent_field.name:_parent_field})
                        _entry.form.rdfFieldList = _entry.form.rdfFieldList + _parent_field_list
                        result.append(self.save_form(_entry.form))
                        #print("mmmmmmmmmm   \n",_entry.form.__dict__)
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
         
        if rdf_form.subform:
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
        print("\tLoading application defaults")
        _sparql = render_without_request(
            "jsonApplicationDefaults.rq",
            graph=FRAMEWORK_CONFIG.get('RDF_DEFINITION_GRAPH'))
        _form_list = requests.post(FRAMEWORK_CONFIG.get('TRIPLESTORE_URL'),
                                   data={"query": _sparql, "format": "json"})
        return json.loads(_form_list.json().get('results').get('bindings'\
                )[0]['app']['value'])

    def _load_rdf_class_defintions(self):
        ''' Queries the triplestore for list of classes used in the app as
            defined in the kl_app.ttl file'''
        print("\tLoading rdf class definitions")
        _sparql = render_without_request("jsonRdfClassDefinitions.rq",
                                         graph=FRAMEWORK_CONFIG.get(\
                                                'RDF_DEFINITION_GRAPH'))
        _class_list = requests.post(FRAMEWORK_CONFIG.get('TRIPLESTORE_URL'),
                                    data={"query": _sparql, "format": "json"})
        return json.loads(_class_list.json().get('results').get('bindings'\
                )[0]['appClasses']['value'])

    def _load_rdf_form_defintions(self):
        ''' Queries the triplestore for list of forms used in the app as
            defined in the kl_app.ttl file'''
        print("\tLoading form definitions")
        _sparql = render_without_request("jsonFormQueryTemplate.rq",
                                         graph=FRAMEWORK_CONFIG.get(\
                                                'RDF_DEFINITION_GRAPH'))
        _form_list = requests.post(FRAMEWORK_CONFIG.get('TRIPLESTORE_URL'),
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
        subject_uri = kwargs.get("subject_uri", rdf_form.dataSubjectUri)
        _subform_data = {}
        _data_list = kwargs.get("data_list",False)
        _parent_field = None
        # test to see if a subform is in the form
        if rdf_form.subform:
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
            
        print("tttttt subform data\n",json.dumps(_subform_data, indent=4))

        _class_name = self.get_class_name(_class_uri)

        subject_uri = kwargs.get("subject_uri", rdf_form.dataSubjectUri)
        #print("%%%%%%%%%%% subject_uri: ",subject_uri)
        _sparql_args = None
        _class_links = self.get_form_class_links(rdf_form)
        _sparql_constructor = dict.copy(_class_links['dependancies'])
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
            print(_sparql)
            # query the triplestore
            code_timer().log("loadOldData", "pre send query")
            _form_data_query =\
                    requests.post(FRAMEWORK_CONFIG.get('TRIPLESTORE_URL'),
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

class RdfClass(object):
    '''RDF Class for an RDF Class object.
       Used for manipulating and validating an RDF Class subject'''

    def __init__(self, json_obj, class_name):
        self.class_name = None
        self.properties = {}
        for _prop in json_obj:
            setattr(self, _prop, json_obj[_prop])
        setattr(self, "class_name", class_name)

    def save(self, rdf_form, old_form_data, validation_status=True):
        """Method validates and saves passed data for the class

        Args:
            rdf_form -- Current RDF Form class fields
            old_form_data -- Preexisting form data
            validationS

        valid_required_props = self._validate_required_properties(
            rdf_form,
            old_form_data)
        validDependancies = self._validate_dependant_props(
            rdf_form,
            old_form_data)"""
        if not validation_status:
            return self.validate_form_data(rdf_form, old_form_data)

        save_data = self._process_class_data(
            rdf_form,
            old_form_data)
        print("-------------- Save data:\n",json.dumps(dumpable_obj(save_data)))
        save_query = self._generate_save_query(save_data)
        return self._run_save_query(save_query)


    def new_uri(self):
        '''*** to be written ***
        generates a new URI
          -- for fedora generates the container and returns the URI
          -- for blazegraph process will need to be created'''
       #print("generating new URI")

    def validate_form_data(self, rdf_form, old_form_data):
        '''This method will validate whether the supplied form data
           meets the class requirements and returns the results'''
        _validation_steps = {}
        _validation_steps['validRequiredFields'] = \
                self._validate_required_properties(rdf_form, old_form_data)
        _validation_steps['validPrimaryKey'] = \
                self.validate_primary_key(rdf_form, old_form_data)
        _validation_steps['validFieldData'] = \
                self._validate_property_data(rdf_form, old_form_data)
        _validation_steps['validSecurity'] =  \
                self._validate_security(rdf_form, old_form_data)
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

    def validate_primary_key(self, rdf_form, old_data=None):
        '''query to see if PrimaryKey is Valid'''
        if old_data is None:
            old_data = {}
        try:
            pkey = make_list(self.primaryKey)
            #print(self.classUri, " PrimaryKeys: ", pkey, "\n")
            if len(pkey) < 1:
                return ["valid"]
            else:
                _calculated_props = self._get_calculated_properties()
                _old_class_data = self._select_class_query_data(old_data)
                #print("pkey _old_class_data: ", _old_class_data, "\n\n")
                _new_class_data = {}
                _query_args = [make_triple("?uri", "a", iri(self.classUri))]
                _multi_key_query_args = [make_triple("?uri", "a", iri(self.classUri))]
                _key_changed = False
                _field_name_list = []
                # get primary key data from the form data
                for prop in rdf_form:
                    if prop['fieldJson'].get("propUri") in pkey:
                        _new_class_data[prop['fieldJson'].get("propUri")] = \
                                prop['data']
                        _field_name_list.append(prop['fieldJson'].get( \
                                "formLabelName", ''))
                #print("pkey _new_class_data: ", _new_class_data, "\n\n")
                for key in pkey:
                    #print("********************** entered key loop")
                    #print("old-new: ", _old_class_data.get(key), " -- ",
                          #_new_class_data.get(key), "\n")
                    _object_val = None
                    #get the _data_value to test against
                    _data_value = _new_class_data.get(key, _old_class_data.get(key))
                    #print("dataValue: ", _data_value)
                    if is_not_null(_data_value):
                        #print("********************** entered _data_value if",
                         #     "-- propName: ", self.find_prop_name(key))

                        _data_type = self.properties.get(self.find_prop_name(key)\
                                ).get("range", [])[0].get('storageType')
                        #print("_data_type: ", _data_type)
                        if _data_type == 'literal':
                            _data_type = self.properties.get(self.find_prop_name( \
                                    key)).get("range", [])[0].get('rangeClass')
                            _object_val = RdfDataType(_data_type).sparql(_data_value)
                        else:
                            _object_val = iri(_data_value)
                    #print("objectVal: ", _object_val)
                    # if the old_data is not equel to the newData re-evaluate
                    # the primaryKey
                    if (_old_class_data.get(key) != _new_class_data.get(key))\
                            and (key not in _calculated_props):
                        _key_changed = True
                        if _object_val:
                            _query_args.append(make_triple("?uri", iri(key), \
                                    _object_val))
                            _multi_key_query_args.append(make_triple("?uri", \
                                    iri(key), _object_val))
                    else:
                        if _object_val:
                            _multi_key_query_args.append(make_triple("?uri", \
                                    iri(key), _object_val))
                #print("\n////////////////// _query_args:\n", _query_args)
                #print("               _multi_key_query_args:\n", _multi_key_query_args)
                #print("               _key_changed: ", _key_changed)
                # if the primary key changed in the form we need to
                # query to see if there is a violation with the new value
                if _key_changed:
                    if len(pkey) > 1:
                        args = _multi_key_query_args
                    else:
                        args = _query_args
                    sparql = '''{}\nSELECT (COUNT(?uri)>0 AS ?keyViolation)
{{\n{}\n}}\nGROUP BY ?uri'''.format(get_framework().get_prefix(),
                                    "\n".join(args))

                    _key_test_results =\
                            requests.post(\
                                    FRAMEWORK_CONFIG.get('TRIPLESTORE_URL'),
                                    data={"query": sparql, "format": "json"})
                    #print("_key_test_results: ", _key_test_results.json())
                    _key_test = _key_test_results.json().get('results').get( \
                            'bindings', [])
                    #print(_key_test)
                    #print(json.dumps(_key_test[0], indent=4))
                    if len(_key_test) > 0:
                        _key_test = _key_test[0].get('keyViolation', {}).get( \
                                'value', False)
                    else:
                        _key_test = False

                    #print("----------- PrimaryKey query:\n", sparql)
                    if not _key_test:
                        return ["valid"]
                    else:
                        return [{"errorType":"primaryKeyViolation",
                                 "formErrorMessage": \
                                        "This {} aleady exists.".format(
                                            " / ".join(_field_name_list)),
                                            "errorData":{
                                                "class":self.classUri,
                                                "propUri":pkey}}]
                return ["valid"]
        except:
            return ["valid"]
        else:
            return ["valid"]

    def list_required(self):
        '''Returns a set of the required properties for the class'''
        _required_list = set()
        for _prop in self.properties:
            if self.properties[_prop].get('requiredByDomain') == self.classUri:
                _required_list.add(self.properties[_prop].get('propUri'))
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
        for p in self.properties:
            property_list.add(self.properties[p].get('propUri'))
        return property_list

    def list_dependant(self):
        '''Returns a set of properties that are dependent upon the
        creation of another object'''
        _dependent_list = set()
        for _prop in self.properties:
            _range_list = self.properties[_prop].get('range')
            for _row in _range_list:
                if _row.get('storageType') == "object" or \
                        _row.get('storageType') == "blanknode":
                    _dependent_list.add(_prop)
        _return_obj = []
        for _dep in _dependent_list:
            _range_list = self.properties[_dep].get('range')
            for _row in _range_list:
                if _row.get('storageType') == "object" or \
                   _row.get('storageType') == "blanknode":
                    _return_obj.append(
                        {"propName": _dep,
                         "propUri": self.properties[_dep].get("propUri"),
                         "classUri": _row.get("rangeClass")})
        return _return_obj

    def find_prop_name(self, prop_uri):
        "cycle through the class properties object to find the property name"
        #print(self.properties)
        try:
            for _prop in self.properties:
                #print("p--", p, " -- ", self.properties[p]['propUri'])
                if self.properties[_prop]['propUri'] == prop_uri:
                   ##print ('propName is ', p)
                    return _prop
        except:
            return None

    def get_property(self, **kwargs):
        '''Method returns the property json object

        keyword Args:
            prop_name: The Name of the property
            prop_uri: The URI of the property
            ** the PropName or URI is required'''

        _prop_name = kwargs.get("prop_name")
        _prop_uri = kwargs.get("prop_uri")
        #print(self.properties)
        if _prop_uri:
            _prop_name = self.find_prop_name(_prop_uri)
        #print(self.__dict__)
        try:
            return self.properties.get(_prop_name)
        except:
            return None


    def _validate_required_properties(self, rdf_form, old_data):
        '''Validates whether all required properties have been supplied and
            contain data '''
        _return_error = []
        #create sets for evaluating requiredFields
        _required = self.list_required()
        _data_props = set()
        _deleted_props = set()
        for prop in rdf_form:
            #remove empty data properties from consideration
            #print(prop,"\n")
            if is_not_null(prop['data']) or prop['data'] != 'None':
                _data_props.add(prop['fieldJson'].get("propUri"))
            else:
                _deleted_props.add(prop['fieldJson'].get("propUri"))
        # find the properties that already exist in the saved class data
        _old_class_data = self._select_class_query_data(old_data)
        for _prop in _old_class_data:
            # remove empty data properties from consideration
            if is_not_null(_old_class_data[_prop]) or _old_class_data[_prop] != 'None':
                _data_props.add(_prop)
        # remove the _deleted_props from consideration and add calculated props
        _valid_props = (_data_props - _deleted_props).union( \
                self._get_calculated_properties())
        #Test to see if all the required properties are supplied
        missing_required_properties = _required - _valid_props
        #print("@@@@@ missing_required_properties: ", missing_required_properties)
        if len(missing_required_properties) > 0:
            _return_error.append({
                "errorType":"missing_required_properties",
                "errorData":{
                    "class":self.classUri,
                    "properties":make_list(missing_required_properties)}})
        if len(_return_error) > 0:
            _return_val = _return_error
        else:
            _return_val = ["valid"]
        #print("_validate_required_properties - ", self.classUri, " --> ", \
                #_return_val)
        return _return_val

    def _get_calculated_properties(self):
        '''lists the properties that will be calculated if no value is
           supplied'''
        _calc_list = set()

        _value_processors = get_framework().value_processors
        #print("_value_processors: ", _value_processors)
        for _prop in self.properties:
            # Any properties that have a default value will be generated at
            # time of save
            if is_not_null(self.properties[_prop].get('defaultVal')):
                _calc_list.add(self.properties[_prop].get('propUri'))
            _processors = make_list(self.properties[_prop].get('propertyProcessing', \
                    []))
            # find the processors that will generate a value
            for _processor in _processors:
                #print("processor: ", processor)
                if _processor in _value_processors:

                    _calc_list.add(self.properties[_prop].get('propUri'))
        #any dependant properties will be generated at time of save
        _dependent_list = self.list_dependant()
        for _prop in _dependent_list:
            _calc_list.add(_prop.get("propUri"))
        return _calc_list

    def _validate_dependant_props(self, rdf_form, old_data):
        '''Validates that all supplied dependant properties have a uri as an
            object'''
        # dep = self.list_dependant()
        # _return_error = []
        _data_props = set()
        for _prop in rdf_form:
            #remove empty data properties from consideration
            if is_not_null(_prop['data']):
                _data_props.add(self.find_prop_name(_prop['fieldJson'].get("propUri")))
        '''for p in dep:
            _data_value = data.get(p)
            if (is_not_null(_data_value)):
                propDetails = self.properties[p]
                r = propDetails.get('range')
                literalOk = false
                for i in r:
                    if i.get('storageType')=='literal':
                        literalOk = True
                if not is_valid_object(_data_value) and not literalOk:
                    _return_error.append({
                        "errorType":"missingDependantObject",
                        "errorData":{
                            "class":self.classUri,
                            "properties":propDetails.get('propUri')}})
        if len(_return_error) > 0:
            return _return_error
        else:'''
        return ["valid"]

    def _select_class_query_data(self, old_data):
        '''Find the data in query data that pertains to this class instance

        returns dictionary of data with the subject_uri stored as
                !!!!subject'''

        #print("__________ class queryData:\n", \
        #                        json.dumps(dumpable_obj(old_data), indent=4))
        _old_class_data = {}
        if old_data.get("queryData"):
            # find the cuurent class data from in the query
            for _subject_uri in old_data.get("queryData"):
                ##print("\t\t subject_uri: ", subject_uri, " subjectClass: ", \
                #old_data['queryData'][subject_uri].get(\
                    #"http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
                #    "\n \t\t\tclassUri: ", self.classUri)
                _class_types = make_list(old_data['queryData'][_subject_uri].get( \
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", []))
                for _rdf_type in _class_types:
                    _class_test = iri(self.classUri)
                    if _rdf_type == _class_test:
                        _old_class_data = old_data['queryData'][_subject_uri]
                        _old_class_data["!!!!subjectUri"] = _subject_uri
                    break
        print("~~~~~~~~~~~~~~~~~ _old_class_data:\n", \
              json.dumps(dumpable_obj(_old_class_data), indent=4))
        return _old_class_data

    def _validate_property_data(self, rdf_form, old_data):
        return ["valid"]

    def _validate_security(self, rdf_form, old_data):
        return ["valid"]

    def _process_class_data(self, rdf_form, old_data_obj):
        '''Reads through the processors in the defination and processes the
            data for saving'''
        _pre_save_data = {}
        _save_data = {}
        _processed_data = {}
        obj = {}
        _required_props = self.list_required()
        _calculated_props = self._get_calculated_properties()
        _old_data = self._select_class_query_data(old_data_obj)
        subject_uri = _old_data.get("!!!!subjectUri", "<>")
        # cycle through the form class data and add old, new, doNotSave and
        # processors for each property
        #print("****** _old_data:\n",\
                #json.dumps(dumpable_obj(_old_data), indent=4))
        for prop in rdf_form:
            _prop_uri = prop.get('fieldJson', {}).get('propUri')
            # gather all of the processors for the proerty
            _class_prop = self.get_property(\
                    prop_uri=prop['fieldJson'].get("propUri"))
            _class_prop_processors = set(clean_processors(make_list(\
                    _class_prop.get("propertyProcessing"))))
            _form_prop_processors = set(clean_processors(make_list(\
                    prop['fieldJson'].get("processors"))))
            processors = remove_null(\
                    _class_prop_processors.union(_form_prop_processors))
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
                        {"new":prop.get('data'),
                         "old":_old_data.get(_prop_uri),
                         "className": self.class_name,
                         "required": _required_prop,
                         "editable": prop['fieldJson'].get("editable", True),
                         "doNotSave": prop['fieldJson'].get("doNotSave", False),
                         "processors": processors}
            else:
                _temp_list = make_list(_pre_save_data[_prop_uri])
                _temp_list.append(\
                        {"new":prop.get('data'),
                         "old":_old_data.get(_prop_uri),
                         "className": self.class_name,
                         "required": _required_prop,
                         "editable": prop['fieldJson'].get("editable", True),
                         "doNotSave": prop['fieldJson'].get("doNotSave", False),
                         "processors": processors})
                _pre_save_data[_prop_uri] = _temp_list
        # now deal with missing required properties. cycle through the
        # remaing properties and add them to the _pre_save_data object
        for _prop_uri in _required_props:
            #print("########### _required_props: ")
            _class_prop = self.get_property(prop_uri=_prop_uri)
            #print(_class_prop)
            _class_prop_processors =\
                    remove_null(make_set(clean_processors(make_list(\
                            _class_prop.get("propertyProcessing")))))
            # remove the prop from the remaining calculated props
            if _prop_uri in _calculated_props:
                _calculated_props.remove(_prop_uri)
            if not _pre_save_data.get(_prop_uri):
                _pre_save_data[_prop_uri] =\
                        {"new":NotInFormClass(),
                         "old":_old_data.get(_prop_uri),
                         "doNotSave":False,
                         "className": self.class_name,
                         "required": True,
                         "editable": True,
                         "processors":_class_prop_processors,
                         "defaultVal":_class_prop.get("defaultVal"),
                         "calculation": _class_prop.get("calculation")}
                #print("psave: ", _pre_save_data[_prop_uri])
            else:
                _temp_list = make_list(_pre_save_data[_prop_uri])
                _pre_save_data[_prop_uri] = _temp_list.append(\
                        {"new":NotInFormClass(),
                         "old":_old_data.get(_prop_uri),
                         "doNotSave": False,
                         "className": self.class_name,
                         "editable": True,
                         "processors":_class_prop_processors,
                         "defaultVal":_class_prop.get("defaultVal"),
                         "calculation": _class_prop.get("calculation")})

        # now deal with missing calculated properties. cycle through the
        # remaing properties and add them to the _pre_save_data object
        #print("calc props: ", _calculated_props)
        for _prop_uri in _calculated_props:
            #print("########### _calculated_props: ")
            _class_prop = self.get_property(prop_uri=_prop_uri)
            _class_prop_processors = remove_null(make_set(\
                            clean_processors(make_list(\
                                    _class_prop.get("propertyProcessing")))))
            if not _pre_save_data.get(_prop_uri):
                _pre_save_data[_prop_uri] =\
                        {"new":NotInFormClass(),
                         "old":_old_data.get(_prop_uri),
                         "doNotSave":False,
                         "processors":_class_prop_processors,
                         "defaultVal":_class_prop.get("defaultVal"),
                         "calculation": _class_prop.get("calculation")}
            else:
                _temp_list = make_list(_pre_save_data[_prop_uri])
                _pre_save_data[_prop_uri] =\
                        _temp_list.append(\
                                {"new":NotInFormClass(),
                                 "old":_old_data.get(_prop_uri),
                                 "doNotSave":False,
                                 "processors":_class_prop_processors,
                                 "defaultVal":_class_prop.get("defaultVal"),
                                 "calculation": _class_prop.get("calculation")})

        #print(json.dumps(dumpable_obj(_pre_save_data), indent=4))
        #print("_________________________________________________")
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
            #doNotSave = prop.get("doNotSave", False)
        for _prop_uri, _prop in _pre_save_data.items():
            # send each property to be proccessed
            if _prop:
                obj = self._process_prop({"propUri":_prop_uri,
                                          "prop": _prop,
                                          "processedData": _processed_data,
                                          "preSaveData": _pre_save_data})
                _processed_data = obj["processedData"]
                _pre_save_data = obj["preSaveData"]

        _save_data = {"data":self.__format_data_for_save(_processed_data,
                                                         _pre_save_data),
                      "subjectUri":subject_uri}

        print(json.dumps(dumpable_obj(_pre_save_data), indent=4))

        return _save_data

    def _generate_save_query(self, save_data_obj, subject_uri=None):
        _save_data = save_data_obj.get("data")
        # find the subject_uri positional argument or look in the save_data_obj
        # or return <> as a new node
        if not subject_uri:
            subject_uri = iri(save_data_obj.get('subjectUri', "<>"))
        _save_type = self.storageType
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
                _prop_set.add(prop[0])
                _prop_iri = iri(prop[0])
                if not isinstance(prop[1], DeleteProperty):
                    _insert_clause += "{}\n".format(\
                                        make_triple(subject_uri, _prop_iri, prop[1]))
                    _bn_insert_clause.append("\t{} {}".format(_prop_iri, prop[1]))
            if subject_uri != '<>':
                for prop in _prop_set:
                    _prop_iri = iri(prop)
                    _delete_clause += "{}\n".format(\
                                    make_triple(subject_uri, _prop_iri, "?"+str(i)))
                    _where_clause += "OPTIONAL {{ {} }} .\n".format(\
                                    make_triple(subject_uri, _prop_iri, "?"+str(i)))
                    i += 1
            else:
                _insert_clause += make_triple(subject_uri, "a", iri(self.classUri)) + \
                        "\n"
                _bn_insert_clause.append("\t a {}".format(iri(self.classUri)))
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
                        prefix=get_framework().get_prefix(),
                        _delete_clause=_delete_clause,
                        _insert_clause=_insert_clause,
                        _where_clause=_where_clause)
                else:
                    _save_query = "{}\n\n{}".format(
                        get_framework().get_prefix("turtle"),
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
                        FRAMEWORK_CONFIG.get("REPOSITORY_URL"),
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

    def find_prop_name(self, prop_uri):
        "cycle through the class properties object to find the property name"
        #print(self.properties)
        for _prop in self.properties:
            #print("p--", p, " -- ", self.properties[p]['propUri'])
            if self.properties[_prop]['propUri'] == prop_uri:
                return _prop

    def _process_prop(self, obj):
        # obj = propUri, prop, processedData, _pre_save_data
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
                    for processor in processors:
                        obj = run_processor(processor, obj)
                # if the processors did not calculate a value for the
                # property attempt to calculte from the default
                # property settings
                if not obj['prop'].get('calcValue', False):
                    obj = self.__calculate_property(obj)
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
                        for processor in processors:
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
            _keep_image = i
            if isinstance(prop['new'], FileStorage):
                if prop['new'].filename:
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
        _save_data = []
        #print("format data***********\n", json.dumps(dumpable_obj(processed_data), indent=4))
        for _prop_uri, prop in processed_data.items():
            if isinstance(prop, DeleteProperty):
                _save_data.append([_prop_uri, prop])
            elif isinstance(prop, FileStorage):
                _file_iri = save_file_to_repository(\
                        prop, pre_save_data[_prop_uri][0].get('old'))
                _save_data.append([_prop_uri, _file_iri])
            else:
                _prop_name = self.find_prop_name(_prop_uri)
                _data_type = self.properties[_prop_name].get("range", [{}])[0].get(\
                                                                'storageType')
                if _data_type == 'literal':
                    _data_type = self.properties[_prop_name].get(\
                                "range", [{}])[0].get('rangeClass', _data_type)
                _value_list = make_list(prop)
                for item in _value_list:
                    if _data_type in ['object', 'blanknode']:
                        _save_data.append([_prop_uri, iri(item)])
                    else:
                        _save_data.append([_prop_uri, RdfDataType(\
                                    _data_type).sparql(str(item))])
        return _save_data

class RdfDataType(object):
    "This class will generate a rdf data type"

    def __init__(self, rdf_data_type=None, **kwargs):
        if rdf_data_type is None:
            _class_uri = kwargs.get("class_uri")
            _prop_uri = kwargs.get("prop_uri")
            if _prop_uri:
                rdf_data_type = self._find_type(_class_uri, _prop_uri)
        self.lookup = rdf_data_type
        #! What happens if none of these replacements?
        val = self.lookup.replace(str(XSD), "").\
                replace("xsd:", "").\
                replace("rdf:", "").\
                replace(str(RDF), "")
        if "http" in val:
            val = "string"
        self.prefix = "xsd:{}".format(val)
        self.iri = iri("{}{}".format(str(XSD), val))
        self.name = val
        if val.lower() == "literal" or val.lower() == "langstring":
            self.prefix = "rdf:{}".format(val)
            self.iri = iri(str(RDF) + val)
        elif val.lower() == "object":
            self.prefix = "objInject"
            #! Why is uri a new property if an object?
            self.uri = "objInject"

    def sparql(self, data_value):
        "formats a value for a sparql triple"
        if self.name == "object":
            return iri(data_value)
        elif self.name == "literal":
            return '"{}"'.format(data_value)
        elif self.name == "boolean":
            return '"{}"^^{}'.format(str(data_value).lower(),
                                     self.prefix)
        else:
            return '"{}"^^{}'.format(data_value, self.prefix)

    def _find_type(self, class_uri, prop_uri):
        '''find the data type based on class_uri and prop_uri'''
        _rdf_class = getattr(get_framework(),
                             get_framework().get_class_name(class_uri))
        _range = _rdf_class.get_property(prop_uri=prop_uri).get("range")[0]
        _range.get("storageType")
        if _range.get("storageType") == "literal":
            _range = _range.get("rangeClass")
        else:
            _range = _range.get("storageType")
        return _range




def iri(uri_string):
    "converts a string to an IRI or returns an IRI if already formated"
    if uri_string[:1] == "[":
        return uri_string
    if uri_string[:1] != "<":
        uri_string = "<{}".format(uri_string.strip())
    if uri_string[len(uri_string)-1:] != ">":
        uri_string = "{}>".format(uri_string.strip())
    return uri_string

def is_not_null(value):
    ''' test for None and empty string '''
    return value is not None and len(str(value)) > 0

def is_valid_object(uri_string):
    '''Test to see if the string is a object store'''
    uri_string = uri_string
    return True

def run_processor(processor, obj, mode="save"):
    '''runs the passed in processor and returns the saveData'''
    processor = processor.replace(\
            "http://knowledgelinks.io/ns/data-resources/", "kdr:")

    if processor == "kdr:SaltProcessor":
        return salt_processor(obj, mode)

    elif processor == "kdr:PasswordProcessor":
        return password_processor(obj, mode)

    elif processor == "kdr:CalculationProcessor":
        return calculation_processor(obj, mode)

    elif processor == "kdr:CSVstringToMultiPropertyProcessor":
        return csv_to_multi_prop_processor(obj, mode)

    elif processor == "kdr:AssertionImageBakingProcessor":
        return assert_img_baking_processor(obj, mode)

    elif processor == "kdr:EmailVerificationProcessor":
        return email_verification_processor(obj, mode)

    else:
        if mode == "load":
            return obj.get("dataValue")
        elif mode == "save":
            return obj
        return obj

def assert_img_baking_processor(obj, mode="save"):
    ''' Application sends badge image to the a badge baking service with the
        assertion.'''
    if mode == "load":
        return obj.get("dataValue")
    return obj

def csv_to_multi_prop_processor(obj, mode="save"):
    ''' Application takes a CSV string and adds each value as a separate triple
        to the class instance.'''
    if mode == "save":
        _value_string = obj['prop']['new']
        if is_not_null(_value_string):
            vals = list(make_set(make_list(_value_string.split(', '))))
            obj['processedData'][obj['propUri']] = vals
        obj['prop']['calcValue'] = True
        return obj
    elif mode == "load":
        return ", ".join(obj.get("dataValue"))
    return obj

def email_verification_processor(obj, mode="save"):
    ''' Application application initiates a proccess to verify the email
        address is a valid working address.'''
    if mode == "load":
        return obj.get("dataValue")
    return obj

def save_file_to_repository(data, repo_item_address):
    ''' saves a file from a form to a repository'''
    object_value = ""
    if repo_item_address:
        print("~~~~~~~~ write code here")
    else:
        repository_result = requests.post(
            FRAMEWORK_CONFIG.get("REPOSITORY_URL"),
            data=data.read(),
			         headers={"Content-type":"'image/png'"})
        object_value = repository_result.text
    return iri(object_value)

def password_processor(obj, mode="save"):
    """Function handles application password actions

    Returns:
        modified passed in obj
    """
    if mode in ["save", "verify"]:
        # find the salt property
        salt_url = "http://knowledgelinks.io/ns/data-resources/SaltProcessor"
        _class_name = obj['prop'].get("className")
        _class_properties = getattr(get_framework(), _class_name).properties
        salt_property = None
        # find the property Uri that stores the salt value
        for _prop_name, _class_prop in _class_properties.items():
            if _class_prop.get("propertyProcessing") == salt_url:
                salt_property = _class_prop.get("propUri")
        # if in save mode create a hashed password
        if mode == "save":
            # if the there is not a new password in the data return the obj
            if is_not_null(obj['prop']['new']) or obj['prop']['new'] != 'None':
                # if a salt has not been created call the salt processor
                if not obj['processedData'].get(salt_property):
                    obj = salt_processor(obj, mode, salt_property=salt_property)
                # create the hash
                salt = obj['processedData'].get(salt_property)
                _hash_value = sha256_crypt.encrypt(obj['prop']['new']+salt)
                # assign the hashed password to the processedData
                obj['processedData'][obj['propUri']] = _hash_value
                obj['prop']['calcValue'] = True
            return obj
        # if in verify mode - look up the hash and return true or false
        elif mode == "verify":
            return sha256_crypt.verify(obj['password']+obj['salt'], obj['hash'])
    if mode == "load":
        return obj.get("dataValue")
    return obj

def salt_processor(obj, mode="save", **kwargs):
    '''Generates a random string for salting'''
    if mode == "load":
        return obj.get("dataValue")
    length = 32
    obj['prop']['calcValue'] = True
    # if called from the password processor the kwargs will have a
    # salt_property and we can automatically generate a new one
    if kwargs.get('salt_property'):
        obj['processedData'][kwargs['salt_property']] = \
                        b64encode(os.urandom(length)).decode('utf-8')
        return obj
    # if the salt already exists in the processed data return the obj
    # the processor may have been called by the password processor
    if is_not_null(obj['processedData'].get(obj['propUri'])):
        return obj

    # find the password property
    _class_name = obj['prop'].get("className")
    _class_properties = getattr(get_framework(), _class_name).properties
    password_property = None
    for _prop_name, _class_prop in _class_properties.items():
        if _class_prop.get("propertyProcessing") == \
                "http://knowledgelinks.io/ns/data-resources/PasswordProcessor":
            password_property = obj['preSaveData'].get(\
                                            _class_prop.get("propUri"))

    # check if there is a new password in the preSaveData
    #                         or
    # if the salt property is required and the old salt is empty
    if password_property is not None:
        if is_not_null(password_property.get('new')) or \
                                    (obj['prop'].get('required') and \
                                            not is_not_null(obj['prop']['old'])):
            obj['processedData'][obj['propUri']] = \
                        b64encode(os.urandom(length)).decode('utf-8')
    elif not is_not_null(obj['prop']['old']):
        obj['processedData'][obj['propUri']] = \
                        b64encode(os.urandom(length)).decode('utf-8')
    obj['prop']['calcValue'] = True
    return obj

def calculation_processor(obj, mode="save"):
    ''' Application should proccess the property according to the rules listed
        in the kds:calulation property.'''

    if mode == "save":
        calculation = obj['prop'].get('calculation')
        if calculation:
            if calculation.startswith("slugify"):
                _prop_uri = calculation[calculation.find("(")+1:\
                                                        calculation.find(")")]
                if not _prop_uri.startswith("http"):
                    _ns = _prop_uri[:_prop_uri.find(":")]
                    name = _prop_uri[_prop_uri.find(":")+1:]
                    _prop_uri = get_app_ns_uri(_ns) + name
                _value_to_slug = obj['processedData'].get(_prop_uri, \
                                        obj['preSaveData'].get(_prop_uri, {}\
                                            ).get('new', None))
                if is_not_null(_value_to_slug):
                    obj['processedData'][obj['propUri']] = slugify(_value_to_slug)
                    obj['prop']['calcValue'] = True
            else:
                pass
    elif mode == "load":
        return obj.get("dataValue")

    return obj

def calculate_default_value(field):
    '''calculates the default value based on the field default input'''
    _calculation_string = field.get("defaultVal")
    _return_val = None
    if _calculation_string:
        _calc_params = _calculation_string.split('+')
        _base = _calc_params[0].strip()
        if len(_calc_params) > 1:
            _add_value = float(_calc_params[1].strip())
        else:
            _add_value = 0
        if _base == 'today':
            _return_val = datetime.datetime.now().date() +\
                    datetime.timedelta(days=_add_value)
        elif _base == 'now':
            _return_val = datetime.datetime.now() +\
                    datetime.timedelta(days=_add_value)
        elif _base == 'time':
            _return_val = datetime.datetime.now().time() +\
                    datetime.timedelta(days=_add_value)
    return _return_val

def get_wtform_field(field, instance=''):
    ''' return a wtform field '''
    _form_field = None
    _field_label = field.get("formLabelName", '')
    #print("______label:", _field_label)
    _field_name = field.get("formFieldName", '')
    _field_type_obj = field.get("fieldType", {})
    if isinstance(_field_type_obj.get('type'), list):
        _field_type_obj = _field_type_obj['type'][0]
    _field_validators = get_wtform_validators(field)
    _field_type = "kdr:" + _field_type_obj.get('type', '').replace( \
            "http://knowledgelinks.io/ns/data-resources/", "")
    _default_val = calculate_default_value(field)
    if _field_type == 'kdr:TextField':
        _form_field = StringField(_field_label,
                                  _field_validators,
                                  description=field.get('formFieldHelp', ''))
    elif _field_type == 'kdr:ServerField':
        _form_field = None
        #form_field = StringField(_field_label, _field_validators, description= \
            #field.get('formFieldHelp', ''))
    elif _field_type == 'kdr:TextAreaField':
        _form_field = TextAreaField(_field_label,
                                    _field_validators,
                                    description=field.get('formFieldHelp', ''))
    elif _field_type == 'kdr:PasswordField':
        #print("!!!! Mode: ", _field_type_obj.get('fieldMode'))
        _field_mode = _field_type_obj.get('fieldMode', '').replace(\
                "http://knowledgelinks.io/ns/data-resources/", "")
        if _field_mode == "InitialPassword":
            _form_field = [{"fieldName":_field_name,
                            "field":PasswordField(_field_label,
                                                  _field_validators,
                                                  description=\
                                                  field.get('formFieldHelp',\
                                                         ''))},
                           {"fieldName":_field_name + "_confirm",
                            "field":PasswordField("Re-enter"),
                            "doNotSave":True}]

        elif _field_mode == "ChangePassword":
            _form_field = [{"fieldName":_field_name + "_old",
                            "field":PasswordField("Current"),
                            "doNotSave":True},
                           {"fieldName":_field_name,
                            "field":PasswordField("New")},
                           {"fieldName":_field_name + "_confirm",
                            "field":PasswordField("Re-enter"),
                            "doNotSave":True}]
        elif _field_mode == "LoginPassword":
            _form_field = PasswordField(_field_label,
                                        _field_validators,
                                        description=\
                                                field.get('formFieldHelp', ''))
    elif _field_type == 'kdr:BooleanField':
        _form_field = BooleanField(_field_label,
                                   _field_validators,
                                   description=field.get('formFieldHelp', ''))
    elif _field_type == 'kdr:FileField':
        _form_field = FileField(_field_label,
                                _field_validators,
                                description=field.get('formFieldHelp', ''))
    elif _field_type == 'kdr:DateField':
        _date_format = get_framework().rdf_app_dict['application'].get(\
                'dataFormats', {}).get('pythonDateFormat', '')
        print("date validators:\n", _field_validators)
        _add_optional = True
        for _val in _field_validators:
            if isinstance(_val, InputRequired):
                _add_optional = False
                break
        if _add_optional:
            _field_validators = [Optional()] + _field_validators

        _form_field = DateField(_field_label,
                                _field_validators,
                                description=field.get('formFieldHelp', ''),
                                default=_default_val,
                                format=_date_format)
    elif _field_type == 'kdr:DateTimeField':
        _form_field = DateTimeField(_field_label,
                                    _field_validators,
                                    description=field.get('formFieldHelp', ''))
    elif _field_type == 'kdr:SelectField':
        #print("--Select Field: ", _field_label, _field_validators, description= \
                #field.get('formFieldHelp', ''))
        _form_field = SelectField(_field_label,
                                  _field_validators,
                                  description=field.get('formFieldHelp', ''))
        #_form_field = StringField(_field_label, _field_validators, description= \
                #field.get('formFieldHelp', ''))
    elif _field_type == 'kdr:ImageFileOrURLField':
        _form_field = [{"fieldName":_field_name +"_image",
                        "field":FileField("Image File")},
                       {"fieldName":_field_name + "_url",
                        "field":StringField("Image Url", [URL])}]
    elif _field_type == 'kdr:SubForm':
        _form_name = get_framework().get_form_name(\
                _field_type_obj.get('subFormUri'))
        _sub_form = FormField(rdf_framework_form_factory(_form_name,
                                                         instance),
                              widget=BsGridTableWidget())
        if "RepeatingSubForm" in _field_type_obj.get("subFormMode"):
            _form_field = FieldList(_sub_form, _field_label, min_entries=1,
                                    widget=RepeatingSubFormWidget())
            setattr(_form_field,"frameworkField","RepeatingSubForm")
        else:
            _form_field = _sub_form
            setattr(_form_field,"frameworkField","subForm")        
        
    else:
        _form_field = StringField(_field_label,
                                  _field_validators,
                                  description=field.get('formFieldHelp', ''))
    #print("--_form_field: ", _form_field)
    return _form_field

def get_wtform_validators(field):
    ''' reads the list of validators for the field and returns the wtforms
        validator list'''
    _field_validators = []
    if field.get('required') is True:
        _field_validators.append(InputRequired())
    _validator_list = make_list(field.get('validators', []))
    for _validator in _validator_list:
        _validator_type = _validator['type'].replace(\
                "http://knowledgelinks.io/ns/data-resources/", "kdr:")
        if _validator_type == 'kdr:PasswordValidator':
            _field_validators.append(
                EqualTo(
                    field.get("formFieldName", '') +'_confirm',
                    message='Passwords must match'))
        if _validator_type == 'kdr:EmailValidator':
            _field_validators.append(Email(message=\
                    'Enter a valid email address'))
        if _validator_type == 'kdr:UrlValidator':
            _field_validators.append(URL(message=\
                    'Enter a valid URL/web address'))
        if _validator_type == 'kdr:UniqueValueValidator':
            _field_validators.append(UniqueValue())
        if _validator_type == 'kdr:StringLengthValidator':
            print("enter StringLengthValidator")
            _string_params = _validator.get('parameters')
            _param_list = _string_params.split(',')
            _param_obj = {}
            for _param in _param_list:
                _new_param = _param.split('=')
                _param_obj[_new_param[0]] = _new_param[1]
            _field_min = int(_param_obj.get('min', 0))
            _field_max = int(_param_obj.get('max', 1028))
            _field_validators.append(Length(
                min=_field_min,
                max=_field_max,
                message="{} size must be between {} and {} characters".format(
                    field.get("formFieldName"),
                    _field_min,
                    _field_max)))
    return _field_validators

def get_field_json(field, instructions, instance, user_info, item_permissions=None):
    '''This function will read through the RDF defined info and proccess the
	json to return the correct values for the instance, security and details'''
    if item_permissions is None:
        item_permissions = []
    _rdf_app = get_framework().rdf_app_dict['application']
    instance = instance.replace(".html", "")
    # Determine Security Access
    _new_field = {}
    _access_level = get_field_security_access(field, user_info, item_permissions)
    if "Read" not in _access_level:
        return None
    _new_field['accessLevel'] = _access_level

    # get form instance info
    _form_instance_info = {}
    _form_field_instance_type_list = make_list(field.get('formInstance', field.get(\
            'formDefault', {}).get('formInstance', [])))
    print("instance type list: ",_form_field_instance_type_list)
    print("instance: ", instance)
    for _field_instance in _form_field_instance_type_list:
        if _field_instance.get('formInstanceType') == instance:
            _form_instance_info = _field_instance
    print("instance info\n",_form_instance_info)
    # Determine the field paramaters
    _new_field['formFieldName'] = _form_instance_info.get('formFieldName', field.get(\
            "formFieldName", field.get('formDefault', {}).get(\
            'formFieldName', "")))
    _new_field['fieldType'] = _form_instance_info.get('fieldType', field.get(\
            'fieldType', field.get('formDefault', {}).get('fieldType', "")))
    if not isinstance(_new_field['fieldType'], dict):
        _new_field['fieldType'] = {"type":_new_field['fieldType']}

    _new_field['formLabelName'] = _form_instance_info.get('formlabelName', \
            field.get("formLabelName", field.get('formDefault', {}).get(\
            'formLabelName', "")))
    _new_field['formFieldHelp'] = _form_instance_info.get('formFieldHelp', \
            field.get("formFieldHelp", field.get('formDefault', {}).get(\
            'formFieldHelp', "")))
    _new_field['formFieldOrder'] = _form_instance_info.get('formFieldOrder', \
            field.get("formFieldOrder", field.get('formDefault', {}).get(\
            'formFieldOrder', "")))
    _new_field['formLayoutRow'] = _form_instance_info.get('formLayoutRow', \
            field.get("formLayoutRow", field.get('formDefault', {}).get(\
            'formLayoutRow', "")))
    _new_field['propUri'] = field.get('propUri')
    _new_field['className'] = field.get('className')
    _new_field['classUri'] = field.get('classUri')
    _new_field['range'] = field.get('range')
    _new_field['defaultVal'] = _form_instance_info.get('defaultVal',\
            field.get('defaultVal'))

    # get applicationActionList
    _new_field['actionList'] = make_set(_form_instance_info.get(\
            'applicationAction', set()))
    _new_field['actionList'].union(make_set(field.get('applicationAction', set())))
    _new_field['actionList'] = list(_new_field['actionList'])
    print("action List:_______________", _new_field['actionList'])
    if "http://knowledgelinks.io/ns/data-resources/RemoveFromForm" in\
            _new_field['actionList']:
        return None
    # get valiator list
    _new_field['validators'] = make_list(_form_instance_info.get('formValidation', []))
    _new_field['validators'] += make_list(field.get('formValidation', []))
    _new_field['validators'] += make_list(field.get('propertyValidation', []))

    # get processing list
    _new_field['processors'] = make_list(_form_instance_info.get('formProcessing', []))
    _new_field['processors'] += make_list(field.get('formProcessing', []))
    _new_field['processors'] += make_list(field.get('propertyProcessing', []))

    # get required state
    _required = False
    if (field.get('propUri') in make_list(field.get('classInfo', {}).get(\
            'primaryKey', []))) or (field.get('requiredField', False)):
        _required = True
    if field.get('classUri') in make_list(field.get('requiredByDomain', {})):
        _required = True
    _new_field['required'] = _required

    # Determine EditState
    if ("Write" in _access_level) and (\
            "http://knowledgelinks.io/ns/data-resources/NotEditable" \
            not in _new_field['actionList']):
        _new_field['editable'] = True
    else:
        _new_field['editable'] = False

    # Determine css classes
    css = _form_instance_info.get('overideCss', field.get('overideCss', \
            instructions.get('overideCss', None)))
    if css is None:
        css = _rdf_app.get('formDefault', {}).get('fieldCss', '')
        css = css.strip() + " " + instructions.get('propertyAddOnCss', '')
        css = css.strip() + " " + _form_instance_info.get('addOnCss', field.get(\
                'addOnCss', field.get('formDefault', {}).get('addOnCss', '')))
        css = css.strip()
    _new_field['css'] = css

    return _new_field

def get_form_instructions_json(instructions, instance):
    ''' This function will read through the RDF defined info and proccess the
        json to retrun the correct instructions for the specified form
        instance.'''

    _rdf_app = get_framework().rdf_app_dict['application']
    #print("inst------", instructions)
# get form instance info
    _form_instance_info = {}
    _form_instance_type_list = make_list(instructions.get('formInstance', []))
    for _form_instance in _form_instance_type_list:
        if _form_instance.get('formInstanceType') == instance:
            _form_instance_info = _form_instance
    _new_instr = {}
    #print("------", _form_instance_info)
#Determine the form paramaters
    _new_instr['formTitle'] = _form_instance_info.get('formTitle', \
            instructions.get("formTitle", ""))
    _new_instr['formDescription'] = _form_instance_info.get('formDescription', \
            instructions.get("formDescription", ""))
    _new_instr['form_Method'] = _form_instance_info.get('form_Method', \
            instructions.get("form_Method", ""))
    _new_instr['form_enctype'] = _form_instance_info.get('form_enctype', \
            instructions.get("form_enctype", ""))
    _new_instr['propertyAddOnCss'] = _form_instance_info.get('propertyAddOnCss', \
            instructions.get("propertyAddOnCss", ""))
    _new_instr['lookupClassUri'] = _form_instance_info.get('lookupClassUri', \
            instructions.get("lookupClassUri", ""))
    _new_instr['lookupPropertyUri'] =\
            _form_instance_info.get('lookupPropertyUri',\
                    instructions.get("lookupPropertyUri", ""))
    _new_instr['submitSuccessRedirect'] = \
            _form_instance_info.get('submitSuccessRedirect',
                                    instructions.get(\
                                            "submitSuccessRedirect", ""))
    _new_instr['submitFailRedirect'] = \
            _form_instance_info.get('submitFailRedirect',
                                    instructions.get("submitFailRedirect", ""))

# Determine css classes
    #form row css
    css = _form_instance_info.get('rowOverideCss', instructions.get(\
            'rowOverideCss', None))
    if css is None:
        css = _rdf_app.get('formDefault', {}).get('rowCss', '')
        css = css.strip() + " " + _form_instance_info.get('rowAddOnCss', \
                instructions.get('rowAddOnCss', ''))
        css = css.strip()
        css.strip()
    _new_instr['rowCss'] = css

    #form general css
    css = _form_instance_info.get('formOverideCss', instructions.get(\
            'formOverideCss', None))
    if css is None:
        css = _rdf_app.get('formDefault', {}).get('formCss', '')
        css = css.strip() + " " + _form_instance_info.get('formAddOnCss', \
                instructions.get('formAddOnCss', ''))
        css = css.strip()
        css.strip()
    _new_instr['formCss'] = css

    return _new_instr

def get_field_security_access(field, user_info, item_permissions=None):
    '''This function will return level security access allowed for the field'''
    if item_permissions is None:
        item_permissions = []
    #Check application wide access
    _app_security = user_info.get('applicationSecurity', set())
    #Check class access
    _class_access_list = make_list(field.get('classInfo', {"classSecurity":[]}\
                ).get("classSecurity", []))
    _class_access = set()
    if len(_class_access_list) > 0:
        for i in _class_access_list:
            if i['agent'] in user_info['userGroups']:
                _class_access.add(i.get('mode'))

    #check property security
    _property_access_list = make_list(field.get('propertySecurity', []))
    _property_access = set()
    if len(_property_access_list) > 0:
        for i in _property_access_list:
            if i['agent'] in user_info['userGroups']:
                _class_access.add(i.get('mode'))

    #check item permissions
    _item_access_list = make_list(field.get('itemSecurity', []))
    _item_access = set()
    if len(_item_access_list) > 0:
        for i in _item_access_list:
            if i['agent'] in user_info['userGroups']:
                _item_access.add(i.get('mode'))

    _main_access = _item_access.intersection(_property_access)
    if "SuperUser" in _app_security:
        return set('Read', 'Write')
    elif len(_main_access) > 0:
        return _main_access
    elif len(_class_access) > 0:
        return _class_access
    elif len(_app_security) > 0:
        return _app_security
    else:
        return set()


def rdf_framework_form_factory(name, instance='', **kwargs):
    ''' Generates a form class based on the form definitions in the
        kds-app.ttl file

    keyword Args:
        class_uri: the classUri used for a form with loaded data
                   ***** has to be the class of the subject_uri for
                         the form data lookup
        subject_uri: the uri of the object that you want to lookup
    '''
    rdf_form = type(name, (Form, ), {})
    _app_form = get_framework().rdf_form_dict.get(name, {})
    fields = _app_form.get('properties')
    instructions = get_form_instructions_json(_app_form.get('formInstructions'), \
            instance)
    _lookup_class_uri = kwargs.get("classUri", instructions.get("lookupClassUri"))
    _lookup_prop_uri = kwargs.get("propUri", instructions.get("lookupPropUri"))
    _lookup_subject_uri = kwargs.get("subject_uri")

    # get the number of rows in the form and define the fieldList as a
    # mulit-demensional list
    _field_list = []
    _form_rows = int(fields[len(fields)-1].get('formLayoutRow', 1))
    for i in range(0, _form_rows):
        _field_list.append([])

    # ************************** Testing Variable *************************
    user_info = {
        "userGroups":[\
                    "http://knowledgelinks.io/ns/data-resources/SysAdmin-SG"],
        'applicationSecurity':["Read", "Write"]
    }
    # *********************************************************************
    _subform = False
    for fld in fields:
        field = get_field_json(fld, instructions, instance, user_info)
        if field:
            _form_row = int(field.get('formLayoutRow', 1))-1
            form_field = get_wtform_field(field, instance)
            if isinstance(form_field, list):
                i = 0
                #print("____----")
                for fld in form_field:
                    #print(fld)
                    if fld.get('field'):
                        _new_field = dict.copy(field)
                        _new_field['formFieldName'] = fld['fieldName']
                        _new_field['formFieldOrder'] = float(_new_field['formFieldOrder']) + i
                        if fld.get("doNotSave"):
                            _new_field['doNotSave'] = True
                        _field_list[_form_row].append(_new_field)
                        #print("--Nfield: ", _new_field)
                        setattr(rdf_form, fld['fieldName'], fld['field'])
                        i += .1
            else:
                #print(field['formFieldName'], " - ", form_field)
                if form_field:
                    #print("set --- ", field)
                    _field_list[_form_row].append(field)
                    setattr(rdf_form, field['formFieldName'], form_field)
                    if hasattr(form_field,"frameworkField"):
                        
                        if "subform" in form_field.frameworkField.lower():
                            _subform = True
    setattr(rdf_form, 'subform', _subform)                        
    setattr(rdf_form, 'rdfFormInfo', _app_form)
    setattr(rdf_form, "rdfInstructions", instructions)
    setattr(rdf_form, "rdfFieldList", list.copy(_field_list))
    setattr(rdf_form, "rdfInstance", instance)
    setattr(rdf_form, "dataClassUri", _lookup_class_uri)
    setattr(rdf_form, "dataSubjectUri", _lookup_subject_uri)
    setattr(rdf_form, "dataPropUri", _lookup_prop_uri)
    #print(json.dumps(dumpable_obj(rdf_form.__dict__),indent=4))
    return rdf_form
    #return rdf_form

def make_list(value):
    ''' Takes a value and turns it into a list if it is not one

    !!!!! This is important becouse list(value) if perfomed on an
    dictionary will return the keys of the dictionary in a list and not
    the dictionay as an element in the list. i.e.
        x = {"first":1, "second":2}
        list(x) = ["first", "second"]
        make_list(x) =[{"first":1, "second":2}]
    '''
    if not isinstance(value, list):
        value = [value]
    return value

def make_set(value):
    ''' Takes a value and turns it into a set

    !!!! This is important because set(string) will parse a string to
    individual characters vs. adding the string as an element of
    the set i.e.
        x = 'setvalue'
        set(x) = {'t', 'a', 'e', 'v', 'u', 's', 'l'}
        make_set(x) = {'setvalue'}
    '''
    _return_set = set()
    if isinstance(value, list):
        for i in value:
            _return_set.add(i)
    elif isinstance(value, set):
        _return_set = value
    else:
        _return_set.add(value)
    return _return_set

def get_framework(**kwargs):
    ''' sets an instance of the the framework as a global variable. This
        this method is then called to access that specific instance '''
    global RDF_GLOBAL
    global FRAMEWORK_CONFIG
    _reset = kwargs.get("reset")
    if FRAMEWORK_CONFIG is None:
        if  kwargs.get("config"):
            config = kwargs.get("config")
        else:
            try:
                config = current_app.config
            except:
                config = None
        if not config is None:
            FRAMEWORK_CONFIG = config
        else:
            return "framework not initialized"
    if _reset:
        RDF_GLOBAL = RdfFramework()
    if RDF_GLOBAL is None:
        RDF_GLOBAL = RdfFramework()
    return RDF_GLOBAL

def query_select_options(field):
    ''' returns a list of key value pairs for a select field '''
    _prefix = get_framework().get_prefix()
    _select_query = field.get('fieldType', {}).get('selectQuery', None)
    _select_list = {}
    _options = []
    if _select_query:
        #print(_prefix+_select_query)
        code_timer().log("formTest", "----Sending query to triplestore")
        # send query to triplestore
        _select_list = requests.post(
            FRAMEWORK_CONFIG.get('TRIPLESTORE_URL'),
            data={"query": _prefix + _select_query,
                  "format": "json"})
        code_timer().log("formTest", "----Recieved query from triplestore")
        _raw_options = _select_list.json().get('results', {}).get('bindings', [])
        _bound_var = field.get('fieldType', {}).get('selectBoundValue', ''\
                ).replace("?", "")
        _display_var = field.get('fieldType', {}).get('selectDisplay', ''\
                ).replace("?", "")
        # format query result into key value pairs
        for row in _raw_options:
            _options.append(
                {
                    "id":iri(row.get(_bound_var, {}).get('value', '')),
                    "value":row.get(_display_var, {}).get('value', '')
                })
    return _options

def load_form_select_options(rdf_form, basepath=""):
    ''' queries the triplestore for the select options

    !!!!!!!!!!!!!! based on performace this needs to be sent to the
    triplestore as one query. Each query to the triplestore is a minimum
    1000+ ms !!!!!!!'''

    for row in rdf_form.rdfFieldList:
        for fld in row:
            if fld.get('fieldType', {}).get('type', "") == \
                    'http://knowledgelinks.io/ns/data-resources/SelectField':
                _options = query_select_options(fld)
                #print("oooooooo\n", options)
                _fld_name = fld.get('formFieldName', None)
                _wt_field = getattr(rdf_form, _fld_name)
                _wt_field.choices = [(_option['id'], _option['value']) \
                        for _option in _options]
                # add an attribute for the displayform with the displayed
                # element name
                if is_not_null(_wt_field.data):
                    for _option in _options:
                        if _option['id'] == _wt_field.data:
                            _form_name = get_framework().get_form_name(\
                                    fld.get("fieldType", {}).get("linkedForm"))
                            if is_not_null(_form_name):
                                _data = "{}'{}{}/{}.{}{}'>{}</a>".format(
                                    "<a href=",
                                    basepath,
                                    _form_name,
                                    "DisplayForm",
                                    "html?id=",
                                    re.sub(r"[<>]", "", _option['id']),
                                    _option['value'])
                            else:
                                _data = _option['value']

                            _wt_field.selectDisplay = _data
                        break

    return rdf_form

def make_triple(sub, pred, obj):
    """Takes a subject predicate and object and joins them with a space
	in between

    Args:
        sub -- Subject
        pred -- Predicate
        obj  -- Object
    Returns
        str
	"""
    return "{s} {p} {o} .".format(s=sub, p=pred, o=obj)

def xsd_to_python(value, data_type, rdf_type="literal"):
    ''' This will take a value and xsd data_type and convert it to a python
        variable'''
    if data_type:
        data_type = data_type.replace(str(XSD), "xsd:")
    if not value:
        return value
    elif rdf_type == "uri":
        return iri(value)
    elif not is_not_null(value):
        return value
    elif data_type == "xsd:anyURI":
        # URI (Uniform Resource Identifier)
        return value
    elif data_type == "xsd:base64Binary":
        # Binary content coded as "base64"
        return value.decode()
    elif data_type == "xsd:boolean":
        # Boolean (true or false)
        if is_not_null(value):
            if lower(value) in ['true', '1', 't', 'y', 'yes', 'yeah', 'yup', \
                    'certainly', 'uh-huh']:
                return True
            elif lower(value) in ['false', '0', 'n', 'no']:
                return False
            else:
                return None
        else:
            return None
    elif data_type == "xsd:byte":
        # Signed value of 8 bits
        return value.decode()
    elif data_type == "xsd:date":
        ## Gregorian calendar date
        _temp_value = parse(value)
        _date_format = get_framework().rdf_app_dict['application'].get(\
                'dataFormats', {}).get('pythonDateFormat', '')
        return _temp_value.strftime(_date_format)
    elif data_type == "xsd:dateTime":
        ## Instant of time (Gregorian calendar)
        return parse(value)
    elif data_type == "xsd:decimal":
        # Decimal numbers
        return float(value)
    elif data_type == "xsd:double":
        # IEEE 64
        return float(value)
    elif data_type == "xsd:duration":
        # Time durations
        return timedelta(milleseconds=float(value))
    elif data_type == "xsd:ENTITIES":
        # Whitespace
        return value
    elif data_type == "xsd:ENTITY":
        # Reference to an unparsed entity
        return value
    elif data_type == "xsd:float":
        # IEEE 32
        return float(value)
    elif data_type == "xsd:gDay":
        # Recurring period of time: monthly day
        return value
    elif data_type == "xsd:gMonth":
        # Recurring period of time: yearly month
        return value
    elif data_type == "xsd:gMonthDay":
        # Recurring period of time: yearly day
        return value
    elif data_type == "xsd:gYear":
        # Period of one year
        return value
    elif data_type == "xsd:gYearMonth":
        # Period of one month
        return value
    elif data_type == "xsd:hexBinary":
        # Binary contents coded in hexadecimal
        return value
    elif data_type == "xsd:ID":
        # Definition of unique identifiers
        return value
    elif data_type == "xsd:IDREF":
        # Definition of references to unique identifiers
        return value
    elif data_type == "xsd:IDREFS":
        # Definition of lists of references to unique identifiers
        return value
    elif data_type == "xsd:int":
        # 32
        return value
    elif data_type == "xsd:integer":
        # Signed integers of arbitrary length
        return int(value)
    elif data_type == "xsd:language":
        # RFC 1766 language codes
        return value
    elif data_type == "xsd:long":
        # 64
        return int(value)
    elif data_type == "xsd:Name":
        # XML 1.O name
        return value
    elif data_type == "xsd:NCName":
        # Unqualified names
        return value
    elif data_type == "xsd:negativeInteger":
        # Strictly negative integers of arbitrary length
        return abs(int(value))*-1
    elif data_type == "xsd:NMTOKEN":
        # XML 1.0 name token (NMTOKEN)
        return value
    elif data_type == "xsd:NMTOKENS":
        # List of XML 1.0 name tokens (NMTOKEN)
        return value
    elif data_type == "xsd:nonNegativeInteger":
        # Integers of arbitrary length positive or equal to zero
        return abs(int(value))
    elif data_type == "xsd:nonPositiveInteger":
        # Integers of arbitrary length negative or equal to zero
        return abs(int(value))*-1
    elif data_type == "xsd:normalizedString":
        # Whitespace
        return value
    elif data_type == "xsd:NOTATION":
        # Emulation of the XML 1.0 feature
        return value
    elif data_type == "xsd:positiveInteger":
        # Strictly positive integers of arbitrary length
        return abs(int(value))
    elif data_type == "xsd:QName":
        # Namespaces in XML
        return value
    elif data_type == "xsd:short":
        # 32
        return value
    elif data_type == "xsd:string":
        # Any string
        return value
    elif data_type == "xsd:time":
        # Point in time recurring each day
        return parse(value)
    elif data_type == "xsd:token":
        # Whitespace
        return value
    elif data_type == "xsd:unsignedByte":
        # Unsigned value of 8 bits
        return value.decode()
    elif data_type == "xsd:unsignedInt":
        # Unsigned integer of 32 bits
        return int(value)
    elif data_type == "xsd:unsignedLong":
        # Unsigned integer of 64 bits
        return int(value)
    elif data_type == "xsd:unsignedShort":
        # Unsigned integer of 16 bits
        return int(value)
    else:
        return value

def convert_spo_to_dict(data, mode="subject"):
    '''Takes the SPAQRL query results and converts them to a python Dict

    mode: subject --> groups based on subject
    '''
    _return_obj = {}
    _list_obj = False
    if mode == "subject":
        for item in data:
            # determine data is list of objects
            _sv = item['s']['value']
            _pv = item['p']['value']

            if item.get('itemID'):
                _list_obj = True
                _iv = item['itemID']['value']
                if _return_obj.get(_iv):
                    if _return_obj[_iv].get(_sv):
                        if _return_obj[_iv][_sv].get(_pv):
                            _obj_list = make_list(\
                                    _return_obj[_iv][_sv][_pv])
                            _obj_list.append(xsd_to_python(item['o']['value'], \
                                    item['o'].get("datatype"), item['o']['type']))
                            _return_obj[_iv][_sv][_pv] = _obj_list
                        else:
                            _return_obj[_iv][_sv][_pv] = \
                                xsd_to_python(item['o']['value'], item['o'].get(\
                                        "datatype"), item['o']['type'])
                    else:
                        _return_obj[_iv][_sv] = {}
                        _return_obj[_iv][_sv][_pv] = \
                                xsd_to_python(item['o']['value'], item['o'].get(\
                                "datatype"), item['o']['type'])
                else:
                    _return_obj[_iv] = {}
                    _return_obj[_iv][_sv] = {}
                    _return_obj[_iv][_sv][_pv] = \
                            xsd_to_python(item['o']['value'], item['o'].get(\
                            "datatype"), item['o']['type'])
                    
            # if not a list of objects
            else:
                if _return_obj.get(_sv):
                    if _return_obj[_sv].get(_pv):
                        _obj_list = make_list(\
                                _return_obj[_sv][_pv])
                        _obj_list.append(xsd_to_python(item['o']['value'], \
                                item['o'].get("datatype"), item['o']['type']))
                        _return_obj[_sv][_pv] = _obj_list
                    else:
                        _return_obj[_sv][_pv] = \
                            xsd_to_python(item['o']['value'], item['o'].get(\
                                    "datatype"), item['o']['type'])
                else:
                    _return_obj[_sv] = {}
                    _return_obj[_sv][_pv] = \
                            xsd_to_python(item['o']['value'], item['o'].get(\
                            "datatype"), item['o']['type'])
        if _list_obj:
            _return_list = []
            for _key, _value in _return_obj.items():
                _return_list.append(_value)
            return _return_list
        else:
            return _return_obj

def remove_null(obj):
    ''' reads through a list or set and strips any null values'''
    if isinstance(obj, set):
        try:
            obj.remove(None)
        except:
            pass
    elif isinstance(obj, list):
        for item in obj:
            if not is_not_null(item):
                obj.remove(item)
    return obj

class DeleteProperty(object):
    ''' dummy class for tagging items to be deleted. This will prevent
    passed in data ever being confused with marking a property for
    deletion. '''
    def __init__(self):
        setattr(self, "delete", True)

class NotInFormClass(object):
    ''' dummy class for tagging properties that were never in a form.
    This will prevent passed in data ever being confused with a property
    that was never in the form. '''
    def __init__(self):
        setattr(self, "notInForm", True)

def slugify(value):
    """Converts to lowercase, removes non-word characters (alphanumerics and
    underscores) and converts spaces to hyphens. Also strips leading and
    trailing whitespace using Django format

    Args:

    """
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '-', value)

def get_app_ns_uri(value):
    ''' looks in the framework for the namespace uri'''
    for _ns in get_framework().rdf_app_dict['application'].get(\
                                                       "appNameSpace", []):
        if _ns.get('prefix') == value:
            return _ns.get('nameSpaceUri')

def clean_iri(uri_string):
    '''removes the <> signs from a string start and end'''
    if isinstance(uri_string, str):
        if uri_string[:1] == "<" and uri_string[len(uri_string)-1:] == ">":
            uri_string = uri_string[1:len(uri_string)-1]
    return uri_string

def clean_processors(processor_list, _class_uri=None):
    ''' some of the processors are stored as objects and need to retrun
        them as a list of string names'''
    _return_list = []
    #print("oprocessor_list __ ", processor_list)
    for item in processor_list:
        if isinstance(item, dict):
            if _class_uri:
                if item.get("appliesTo") == _class_uri:
                    _return_list.append(item.get("propertyProcessing"))
            else:
                _return_list.append(item.get("propertyProcessing"))
        else:
            _return_list.append(item)
    return _return_list

def get_form_redirect_url(rdf_form, state, base_url, current_url, id_value=None):
    ''' formats the redirect url for the form in its current state '''
    if state == "success":
        _url_instructions = rdf_form.rdfInstructions.get("submitSuccessRedirect")
        if not _url_instructions:
            return base_url
    if state == "fail":
        _url_instructions = rdf_form.rdfInstructions.get("submitFailRedirect")
        if not _url_instructions:
            return "!--currentpage"
    if _url_instructions == "!--currentpage":
        return current_url
    elif _url_instructions == \
            "http://knowledgelinks.io/ns/data-resources/DisplayForm":
        _form_name = rdf_form.rdfFormInfo.get("formName")
        return "{}{}/DisplayForm.html?id={}".format(base_url,
                                                    _form_name,
                                                    id_value)
    elif _url_instructions == "!--homepage":
        return base_url
    else:
        return base_url

class UniqueValue(object):
    ''' a custom validator for use with wtforms
        * checks to see if the value already exists in the triplestore'''

    def __init__(self, message=None):
        if not message:
            message = u'The field must be a unique value'
        self.message = message

    def __call__(self, form, field):
        # get the test query
        _sparql = self._make_unique_value_qry(form, field)
        print(_sparql)
        # run the test query
        _unique_test_results = requests.post(\
                FRAMEWORK_CONFIG.get('TRIPLESTORE_URL'),
                data={"query": _sparql, "format": "json"})
        _unique_test = _unique_test_results.json().get('results').get( \
                            'bindings', [])
        # evaluate the results; True result in the query denotes that the
        # value already exists
        if len(_unique_test) > 0:
            _unique_test = _unique_test[0].get(\
                    'uniqueValueViolation', {}).get('value', False)
        else:
            _unique_test = False
        if _unique_test:
            raise ValidationError(self.message)


    def _make_unique_value_qry(self, form, field):
        _sparql_args = []
        # determine the property and class details of the field
        for _row in form.rdfFieldList:
            for _field in _row:
                if _field.get('formFieldName') == field.name:
                    _prop_uri = _field.get("propUri")
                    _class_uri = _field.get("classUri")
                    _class_name = get_framework().get_class_name(_class_uri)
                    _range = _field.get("range")
                    break
        # make the base triples for the query
        if _prop_uri:
            _data_value = RdfDataType(None,
                                      class_uri=_class_uri,
                                      prop_uri=_prop_uri).sparql(field.data)
            _sparql_args.append(make_triple("?uri", "a", iri(_class_uri)))
            _sparql_args.append(make_triple("?uri",
                                            iri(_prop_uri),
                                            _data_value))
        # see if the form is based on a set of triplestore data. if it is
        # remove that triple from consideration in the query
        if hasattr(form, "dataSubjectUri"):
            _subject_uri = form.dataSubjectUri
            _lookup_class_uri = form.dataClassUri
            # if the subject class is the same as the field class
            if _lookup_class_uri == _class_uri and _subject_uri:
                _sparql_args.append("FILTER(?uri!={}) .".format(\
                        iri(_subject_uri)))
            # If not need to determine how the subject is related to the field
            # property
            elif _subject_uri:
                _lookup_class_name = get_framework().get_class_name(\
                        _lookup_class_uri)
                # class links shows the relationship between the classes in a form
                _class_links = get_framework().get_form_class_links(form).get(\
                        "dependancies")
                # cycle through the class links to find the subject linkage
                for _rdf_class in _class_links:
                    for _prop in _class_links[_rdf_class]:
                        if _lookup_class_uri == _prop.get("classUri"):
                            _linked_lookup_class_name = _rdf_class
                            _linked_lookup_prop = _prop.get("propUri")
                            break
                # if there is a direct link between the subject class and
                # field class add the sparql arguments
                if _linked_lookup_class_name == _class_name:
                    _sparql_args.append(\
                            "OPTIONAL{{?uri {} ?linkedUri}} .".format(\
                                    iri(_linked_lookup_prop)))
                else:
                    # find the indirect linkage i.e.
                    #    field in class A that links to class B with a lookup
                    #    subject in class C
                    for _rdf_class in _class_links:
                        for _prop in _class_links[_rdf_class]:
                            if _class_uri == _prop.get("classUri"):
                                _linked_field_class_name = _rdf_class
                                _linked_field_prop = _prop.get("propUri")
                                break
                    if _linked_lookup_class_name == _linked_field_class_name:
                        _sparql_args.append("OPTIONAL {")
                        _sparql_args.append("?pass {} ?uri .".format(\
                                iri(_linked_field_prop)))
                        _sparql_args.append("?pass {} ?linkedUri .".format(\
                                iri(_linked_lookup_prop)))
                        _sparql_args.append("} .")
                _sparql_args.append(\
                        "BIND(IF(bound(?linkedUri),?linkedUri,'') AS ?link)")
                _sparql_args.append("FILTER(?link!={}).".format(\
                        iri(_subject_uri)))
        return '''{}\nSELECT (COUNT(?uri)>0 AS ?uniqueValueViolation)
{{\n{}\n}}\nGROUP BY ?uri'''.format(get_framework().get_prefix(),
                                    "\n\t".join(_sparql_args))


class BsGridTableWidget(object):
    """
    Renders a list of fields as a bootstrap formated table.

    If `with_row_tag` is True, then an enclosing <row> is placed around the
    rows.

    Hidden fields will not be displayed with a row, instead the field will be
    pushed into a subsequent table row to ensure XHTML validity. Hidden fields
    at the end of the field list will appear outside the table.
    """
    def __init__(self, with_section_tag=False):
        self.with_section_tag = with_section_tag

    def __call__(self, field, **kwargs):
        html = []
        if self.with_section_tag:
            kwargs.setdefault('id', field.id)
            html.append('<section class="col-md-6" %s>' % html_params(**kwargs))
        hidden = ''
        _params = html_params(**kwargs)
        for subfield in field:
            if subfield.type == 'CSRFTokenField':
                html.append('<div style="display:none" %s>%s</div>' % (_params,text_type(subfield(class_="form-control"))))
            else:
                html.append('<div class="col-md-2" %s>%s</div>' % (_params,text_type(subfield(class_="form-control"))))
                hidden = ''
        if self.with_section_tag:
            html.append('</section>')
        if hidden:
            html.append(hidden)
        return HTMLString(''.join(html))

class RepeatingSubFormWidget(object):
    """
    Renders a list of fields as a `row` list.

    This is used for fields which encapsulate many inner fields as subfields.
    The widget will try to iterate the field to get access to the subfields and
    call them to render them.

    If `prefix_label` is set, the subfield's label is printed before the field,
    otherwise afterwards. The latter is useful for iterating radios or
    checkboxes.
    """
    def __init__(self, html_tag='div', prefix_label=True):
        assert html_tag in ('ol', 'ul', 'div')
        self.html_tag = html_tag
        self.prefix_label = prefix_label

    def __call__(self, field, **kwargs):
        kwargs.setdefault('id', field.id)
        _params = html_params(**kwargs)
        html = []
        html.append('<%s class="row">' % (self.html_tag))
        for sub_subfield in field[0]:
            if sub_subfield.type != 'CSRFTokenField':
                html.append('<div class="col-md-2">%s</div>' % sub_subfield.label)
        html.append('</%s>' % (self.html_tag))    
        for subfield in field:
            html.append('<%s class="row">%s</%s>' % (self.html_tag,
                                           #_params,
                                           subfield(),
                                           self.html_tag))
        return HTMLString(''.join(html))
