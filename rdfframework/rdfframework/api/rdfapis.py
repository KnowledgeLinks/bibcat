__author__ = "Mike Stabile, Jeremy Nelson"

import datetime
import requests

from .rdfapifields import get_api_field_json, get_api_field
from rdfframework.utilities import cbool, make_list, make_set, code_timer, \
        fw_config, iri, is_not_null, convert_spo_to_dict, uri, pp, \
        convert_obj_to_rdf_namespace, copy_obj, remove_null
from rdfframework import get_framework as rdfw
from rdfframework.sparql import query_select_options, get_data
from rdfframework.processors import run_processor

    
class Api(object):
    ''' This class is used for a rdfframework API '''

    def __init__(self, *args, **kwargs):
        self.id_value = kwargs.get("id_value")
        self.api_changed = False
        self.base_url = kwargs.get("base_url", self.base_url)
        self.current_url = kwargs.get("current_url", self.current_url)  
        self.base_api_url = kwargs.get("base_api_url", self.base_api_url)
        self.api_url = kwargs.get("api_url", self.api_url)
        self.api_uri = self.api_uri
        self.save_state = None
        self.save_subject_uri = None
        self.save_results = None
        self.data_subject_uri = kwargs.get("subject_uri",self.data_subject_uri)     
        self.data_class_uri = self.data_class_uri
        self.has_subobj = self.has_subobj
        self.is_subobj = self.is_subobj                        
        self.rdf_field_list = self.rdf_field_list                
        self.rdf_instructions = self.rdf_instructions            
        self.instance_uri = self.instance_uri                
        self.data_class_uri = self.data_class_uri                          
        self.data_prop_uri = self.data_prop_uri                
        self._set_class_links()
        self._tie_fields_to_field_list()   
        for fld in self.rdf_field_list:
            pretty_data = pp.pformat(fld.__dict__)
            setattr(fld, 'debug_data', pretty_data)
        pretty_data = pp.pformat(self.__dict__)
        self.debug_data = pretty_data
        

    def save(self):
        ''' sends the form to the framework for saving '''
        save_action = self.rdf_instructions.get('kds_saveAction')
        if save_action == "kdr_AuthenticateUser":
            rdfw().user_authentication(self)
        else:
            rdfw().save_obj(self)
    
    def redirect_url(self, id_value=None, **kwargs):
        ''' formats the redirect url for the form in its current state '''
        if id_value is None:
            id_value = self.save_subject_uri
        if self.save_state == "success":
            _url_instructions = self.rdf_instructions.get("kds_submitSuccessRedirect")
            if not _url_instructions:
                return base_url
        elif self.save_state == "fail":
            _url_instructions = self.rdf_instructions.get("submitFailRedirect")
            if not _url_instructions:
                return "!--currentpage"
        if _url_instructions == "!--currentpage":
            return self.current_url
        elif _url_instructions == "!--homepage":
            return "/"
        elif _url_instructions == "!--source":
            return kwargs.get("params", {}).get("source","/")   
        elif _url_instructions is not None:
            _form_url = rdfw().get_form_path(self.form_uri, _url_instructions)
            if _form_url is not None:
                return "{}{}?id={}".format(self.base_url, _form_url, id_value)
            else:
                return _url_instructions
        else:
            return self.base_url
            
    def remove_prop(self, prop):
        ''' removes a prop completely from the form '''
        self.form_changed = True
        for _prop in self.rdf_field_list:
            if _prop == prop:
                self.rdf_field_list.remove(_prop)
        for _rdf_class, _props in self.class_grouping.items():
            for _prop in _props:
                if _prop == prop:
                    self.class_grouping[_rdf_class].remove(_prop)
        x =  getattr(self, prop.kds_apiFieldName)
        del x
        del prop
        self._set_class_links()

    def add_props(self, prop_list):
        ''' adds a new property/field to the form in all the correct
            locations '''
        prop_list = make_list(prop_list)
        self.api_changed = True
        for _prop in prop_list:
            _current_class = _prop.kds_classUri
            setattr(self, _prop.name, _prop)
            self.rdf_field_list.append(_prop)
            if isinstance(self.class_grouping[_current_class], list):
                self.class_grouping[_current_class].append(_prop)
            else:
                self.class_grouping[_current_class] = [_prop]    
        self._set_class_links()
    
    def reset_fields(self):
        ''' fields are moved around during save process and if the validation
            fails this method will return the fields to their original
            locations '''
        if self.api_changed is True:
            # reset the field listing attributes
            self.rdf_field_list = copy_obj(self.original_rdf_field_list)
            self.class_grouping = copy_obj(self.original_class_grouping)
            # reset the class links attribute
            self._set_class_links()
            # call the reset for the subapis
            for fld in self.rdf_field_list:
                if isinstance(fld, ApiList):
                    for api in fld.entries:
                        if isinstance(api, ApiField):
                            api.reset_fields()
                elif isinstance(fld, ApiField):
                            api.reset_fields()
            self.api_changed = False 
               
    def _tie_fields_to_field_list(self):
        ''' add the attributes to the wtforms fields and creates the 
            rdf_field_list and the rdf class groupings '''
        self.class_grouping = {}
        _new_field_list = []
        for _class in self.class_set:
            self.class_grouping[_class] = []
        for field in self.rdf_field_list:
            #field['field'] = getattr(self,field['kds_formFieldName'])
            fld = getattr(self,field['kds_apiFieldName'])
            if fld:
                for attr, value in field.items():
                    setattr(fld, attr, value)
                setattr(fld, 'processed_data', None)
                setattr(fld, 'old_data', None)
                setattr(fld, 'query_data', None)
                setattr(fld, 'subject_uri', None)
            _new_field_list.append(fld)
            if field['kds_classUri'] not in [None, 'kds_NoClass']:
                self.class_grouping[field['kds_classUri']].append(fld)
            field['field'] = getattr(self,field['kds_apiFieldName'])
        self.rdf_field_list = _new_field_list
        self.original_rdf_field_list = copy_obj(_new_field_list)
        self.original_class_grouping = copy_obj(self.class_grouping)
            
    def _set_class_links(self):
        ''' reads the classes used in the form fields and determines the
            linkages between the classes and sets the the following
            attributes:

            self.dep_classes
            self.indep_classes
            self.dependancies
            self.reverse_dependancies
        '''

        _class_set = set()
        # get all of the unique rdf classes in the passed in form
        for _field in self.rdf_field_list:
            if isinstance(_field, dict):
                _class_set.add(_field['kds_classUri'])
            else:
                _class_set.add(_field.kds_classUri)
        _class_set = remove_null(_class_set)
        try:
            _class_set.remove("kds_NoClass")
        except:
            pass
        class_links = rdfw().get_class_links(_class_set)
        self.class_set = _class_set
        self.dep_classes = class_links['dep_classes']
        self.indep_classes = class_links['indep_classes']
        self.dependancies = class_links['dependancies']
        self.reverse_dependancies = class_links['reverse_dependancies']

    def set_obj_data(self, **kwargs):
        ''' sets the data for the current form paramters

        **keyword arguments
        subject_uri: the URI for the subject
        class_uri: the rdf class of the subject
        '''
        _class_uri = kwargs.get("class_uri", self.data_class_uri)
        _lookup_class_uri = _class_uri
        subject_uri = kwargs.get("subject_uri", self.data_subject_uri)
        if not is_not_null(subject_uri):
            self.query_data = {}
            return None
        _subform_data = {}
        _parent_field = None
        # test to see if a sub_obj is part of the form.
        '''if self.has_subobj:
            for _field in self.rdf_field_list:
                if _field.type == 'FieldList':
                    for _entry in _field.entries:
                        if _entry.type == 'FormField':
                            _sub_rdf_obj = _entry.form
                            _parent_field = _field
            # if the sub_obj get its data
            if _sub_rdf_obj:
                _subform_data = _sub_rdf_obj.query_data'''
        # send the form to the query generator and get the query data back
        if kwargs.get('query_data') is None:
            return None
            '''self.query_data = convert_obj_to_rdf_namespace(\
                    convert_spo_to_dict(get_data(self, **kwargs)))'''
        else:
            self.query_data = kwargs.get('query_data')
        _data_value = None
        # cycle through the query data and add the data to the fields
        for _item in make_list(self.query_data):
            for _prop in self.rdf_field_list:
                _prop_uri = _prop.kds_propUri
                _class_uri = iri(uri(_prop.kds_classUri))
                for _subject in _item:
                    if _class_uri in _item[_subject].get("rdf_type"):
                        _prop.query_data = _item[_subject].get(_prop_uri)
                        _prop.subject_uri = _subject
                        for _processor in _prop.kds_processors:
                            run_processor(_processor, self, _prop, "load")
                    if _prop.processed_data is not None:
                        #print(_prop_uri, " __ ", _prop.query_data, "--pro--", _prop.processed_data)
                        _prop.old_data = _prop.processed_data
                        _prop.processed_data = None
                    else:
                        _prop.old_data = _prop.query_data
                        #print(_prop_uri, " __ ", _prop.query_data, "--old--", _prop.old_data)
                    if _prop.data is None and _prop.old_data is not None:
                        _prop.data = _prop.old_data
                #pp.pprint(_prop.__dict__)
    

def get_api_instructions_json(instructions, instance):
    ''' This function will read through the RDF defined info and proccess the
        json to retrun the correct instructions for the specified form
        instance.'''

    _rdf_app = rdfw().app
    #print("inst------", instructions)
# get form instance info
    _api_instance_info = {}
    _api_instance_type_list = make_list(instructions.get('kds_apiInstance', []))
    for _api_instance in _api_instance_type_list:
        if _api_instance.get('kds_apiInstanceType') == instance:
            _api_instance_info = _api_instance
    _new_instr = {}
    #print("------", _form_instance_info)
#Determine the api paramaters
    _new_instr['kds_apiTitle'] = _api_instance_info.get('kds_apiTitle', \
            instructions.get("kds_apiTitle", ""))
    _new_instr['kds_apiDescription'] = _api_instance_info.get('kds_apiDescription', \
            instructions.get("kds_apiDescription", ""))
    _new_instr['kds_apiMethod'] = _api_instance_info.get('kds_apiMethod', \
            instructions.get("kds_apiMethod", ""))
    _new_instr['kds_lookupClassUri'] = _api_instance_info.get('kds_lookupClassUri', \
            instructions.get("kds_lookupClassUri", ""))
    _new_instr['kds_lookupPropertyUri'] =\
            _api_instance_info.get('kds_lookupPropertyUri',\
                    instructions.get("kds_lookupPropertyUri", ""))
    _new_instr['kds_submitSuccessRedirect'] = \
            _api_instance_info.get('kds_submitSuccessRedirect',
                                    instructions.get(\
                                            "kds_submitSuccessRedirect", ""))
    _new_instr['kds_submitFailRedirect'] = \
            _api_instance_info.get('kds_submitFailRedirect',
                                    instructions.get("kds_submitFailRedirect", ""))
    _new_instr['kds_saveAction'] = \
            _api_instance_info.get('kds_saveAction',
                                    instructions.get("kds_saveAction", ""))
    _new_instr['kds_returnType'] = \
            _api_instance_info.get('kds_returnType',
                                    instructions.get("kds_returnType", ""))
    _new_instr['kds_mimeType'] = \
            _api_instance_info.get('kds_mimeType',
                                    instructions.get("kds_mimeType", ""))                                
    return _new_instr


def rdf_framework_api_factory(api_id, **kwargs):
    ''' Generates a form class based on the form definitions in the
        kds-app.ttl file

    keyword Args:
        class_uri: the classUri used for a form with loaded data
                   ***** has to be the class of the subject_uri for
                         the form data lookup
        subject_uri: the uri of the object that you want to lookup
        is_subform: True or False. States whether the form is a subform
                 of another form
    '''
    # find the api name and instance from the url
    _api_location = rdfw().api_exists(api_id)
    # exit factory if form does not exist
    if _api_location is False:
        return None
    _api_uri = _api_location['api_uri']
    _instance = _api_location['api_uri']

    rdf_api = type(_api_uri, (Api, ), {})
    setattr(rdf_api, "api_uri", _api_uri)
    _app_api = rdfw().rdf_api_dict.get(_api_uri, {})
    fields = make_list(_app_api.get('kds_properties'))
    instructions = get_api_instructions_json(\
            _app_api.get('kds_apiInstructions'), _instance)
    _lookup_class_uri = kwargs.get("classUri",\
                                   instructions.get("kds_lookupClassUri"))
    _lookup_prop_uri = kwargs.get("propUri", \
                                  instructions.get("kds_lookupPropUri"))
    _lookup_subject_uri = kwargs.get("subject_uri")
    kwargs['subject_uri'] = _lookup_subject_uri
    kwargs["propUri"] = _lookup_prop_uri
    kwargs["classUri"] = _lookup_class_uri
    # ************************** Testing Variable *************************
    user_info = {
        "kds_userGroups":["kdr_SysAdmin-SG"],
        'kds_applicationSecurity':["acl_Read", "acl_Write"]
    }
    # *********************************************************************
    _has_subobj = False
    rdf_field_list = []
    for fld in fields:
        #print(fld)
        field = get_api_field_json(fld, instructions, _instance, user_info)
        if field:
            field_item = get_api_field(field, _instance, **kwargs)
            api_field = field_item.get('fld')
            field = field_item.get('fld_json')
            if isinstance(api_field, list):
                i = 0
                for nfld in api_field:
                    #print(fld)
                    if nfld.get('kds_field'):
                        _new_field = dict.copy(field)
                        _new_field['kds_apiFieldName'] = nfld['kds_fieldName']
                        _new_field['kds_apiFieldOrder'] = \
                                float(_new_field['kds_apiFieldOrder']) + i
                        if fld.get("doNotSave"):
                            _new_field['doNotSave'] = True
                        else:
                            _new_field['doNotSave'] = False
                        augmented_field = add_field_attributes(\
                                nfld['kds_field'],_new_field)
                        rdf_field_list.append(_new_field)
                        setattr(rdf_api, nfld['kds_fieldName'], augmented_field)
                        i += .1
            else:
                #print(field['apiFieldName'], " - ", api_field)
                if api_field:
                    #print("set --- ", field)
                    field['doNotSave'] = False
                    rdf_field_list.append(field)
                    setattr(rdf_api, field['kds_apiFieldName'], api_field)

    if kwargs.get("is_subobj"):
        field = {'kds_apiFieldName':'subjectUri',
                 'kds_fieldType':{'rdf_type':'ReferenceField'},
                 'kds_apiLabelName':'Hidden dataSubjectUri',
                 'kds_classUri':_lookup_class_uri,
                 'kds_propUri':'subjectUri',
                 'kds_processors':[],
                 'editable': False,
                 'doNotSave': False}
        rdf_field_list.append(field)
        augmented_field = add_field_attributes(StringField('dataSubjectUri'),
                                               field)
        setattr(rdf_api, 'subjectUri', augmented_field)
        setattr(rdf_api, 'is_subobj', True)
    else:
        setattr(rdf_api, 'is_subobj', False)
    setattr(rdf_api, 'has_subobj', _has_subobj)
    setattr(rdf_api, 'rdf_field_list', rdf_field_list)
    setattr(rdf_api, "rdf_instructions", instructions)
    setattr(rdf_api, "instance_uri", _instance)
    setattr(rdf_api, "data_class_uri", _lookup_class_uri)
    setattr(rdf_api, "data_subject_uri", _lookup_subject_uri)
    setattr(rdf_api, "data_prop_uri", _lookup_prop_uri)
    setattr(rdf_api, "base_url", kwargs.get("base_url"))
    setattr(rdf_api, "current_url", kwargs.get("current_url"))
    setattr(rdf_api, "base_api_url", kwargs.get("base_api_url"))
    setattr(rdf_api, "api_url", kwargs.get("api_url"))
    #pp.pprint(rdf_api.__dict__)
    return rdf_api
    #return rdf_api
