__author__ = "Mike Stabile, Jeremy Nelson"

import datetime
import requests

from rdfframework.validators import UniqueValue
from .rdffields import add_field_attributes, calculate_default_value, \
        get_wtform_field, get_field_json
from wtforms.fields import StringField, FormField, FieldList
import flask_wtf
from rdfframework.utilities import cbool, make_list, make_set, code_timer, \
        fw_config, iri, is_not_null, convert_spo_to_dict, uri, pp, \
        convert_obj_to_rdf_namespace, copy_obj
from rdfframework import get_framework as rdfw
from rdfframework.forms.widgets import BsGridTableWidget, RepeatingSubFormWidget
from rdfframework.sparql import query_select_options, get_data
from rdfframework.processors import run_processor
#Form = flask_wtf.Form
""" NOT IN USE
def form_loader(form_url, **kwargs):
    ''' Main method for starting a form '''
    # create the form class
    form_class = rdf_framework_form_factory(form_url, **kwargs)
    # if there is an id passed in load the data
    subject_uri = kwargs.get("subject_uri")
    if subject_uri:
        form_data = rdfw().get_obj_data(form_class(no_query=True,\
                                                   subject_uri=subject_uri))
    # otherwise set the form_data values to none
    else:
        form_data = {}
        form_data['form_data'] = None
        form_data['query_data'] = None
    # initiate the form with data and paramaters
    form = form_class(form_data['form_data'],\
                      query_data=form_data['query_data'],\
                      subject_uri=subject_uri)
    return form
"""
    
class Form(flask_wtf.Form):
    ''' This class extends the wtforms base form class to add rdfframework
        specific attributes and functions '''

    def __init__(self, *args, **kwargs):
        super(Form, self).__init__(*args, **kwargs)
        self.form_changed = False
        self.base_url = kwargs.get("base_url", self.base_url)
        self.current_url = kwargs.get("current_url", self.current_url)
        self.form_uri = self.form_uri
        self.save_state = None
        self.save_subject_uri = None
        self.save_results = None
        self.data_subject_uri = kwargs.get("subject_uri",self.data_subject_uri)
        self.edit_path = "{}{}?id={}".format(\
                self.base_url,
                rdfw().get_form_path(self.form_uri, "kdr_EditForm"),
                self.data_subject_uri)
        self.display_path = "{}{}?id={}".format(\
                self.base_url,
                rdfw().get_form_path(self.form_uri, "kdr_DisplayForm"),
                self.data_subject_uri)     
        self.data_class_uri = self.data_class_uri
        self.has_subobj = self.has_subobj
        self.is_subobj = self.is_subobj                        
        self.rdf_field_list = self.rdf_field_list                
        self.rdf_instructions = self.rdf_instructions            
        self.instance_uri = self.instance_uri                
        self.data_class_uri = self.data_class_uri                          
        self.data_prop_uri = self.data_prop_uri                
        self._set_class_links()
        self._tie_wtf_fields_to_field_list()
        if not kwargs.get('no_query'):
            #self._get_form_data()
            self._load_form_select_options()      
        for fld in self.rdf_field_list:
            pretty_data = pp.pformat(fld.__dict__)
            setattr(fld, 'debug_data', pretty_data)
        pretty_data = pp.pformat(self.__dict__)
        self.debug_data = pretty_data
        self.original_fields = copy_obj(self._fields)
        

    def save(self):
        ''' sends the form to the framework for saving '''
        rdfw().save_obj(self)
    
    def redirect_url(self, id_value=None):
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
        del self._fields[prop.kds_formFieldName]
        x =  getattr(self, prop.kds_formFieldName)
        del x
        del prop
        self._set_class_links()

    def add_props(self, prop_list):
        ''' adds a new property/field to the form in all the correct
            locations '''
        prop_list = make_list(prop_list)
        self.form_changed = True
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
        if self.form_changed is True:
            # reset the field listing attributes
            self.rdf_field_list = copy_obj(self.original_rdf_field_list)
            self._fields = copy_obj(self.original_fields)
            self.class_grouping = copy_obj(self.original_class_grouping)
            # reset the class links attribute
            self._set_class_links()
            # call the reset for the subforms
            for fld in self.rdf_field_list:
                if isinstance(fld, FieldList):
                    for form in fld.entries:
                        if isinstance(form, FormField):
                            form.reset_fields()
                elif isinstance(fld, FormField):
                            form.reset_fields()
            self.form_changed = False 
               
    def _tie_wtf_fields_to_field_list(self):
        ''' add the attributes to the wtforms fields and creates the 
            rdf_field_list and the rdf class groupings '''
        self.class_grouping = {}
        _new_field_list = []
        for _class in self.class_set:
            self.class_grouping[_class] = []
        for field in self.rdf_field_list:
            #field['field'] = getattr(self,field['kds_formFieldName'])
            fld = getattr(self,field['kds_formFieldName'])
            if fld:
                for attr, value in field.items():
                    setattr(fld, attr, value)
                setattr(fld, 'processed_data', None)
                setattr(fld, 'old_data', None)
                setattr(fld, 'query_data', None)
                setattr(fld, 'subject_uri', None)
            _new_field_list.append(fld)
            self.class_grouping[field['kds_classUri']].append(fld)
            field['field'] = getattr(self,field['kds_formFieldName'])
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

    def _load_form_select_options(self):
        ''' queries the triplestore for the select options and loads the data
        '''
        for fld in self.rdf_field_list:
            if fld.kds_fieldType['rdf_type'] == "kdr_SelectField":
                _options = query_select_options(fld)
                # set the selected options display field to the field
                # attribute "selected_display" this can then be referenced
                # when running a display form.
                for _option in _options:
                    if _option['id'] == fld.data:
                        setattr(fld,"selected_display",_option['value'])
                fld.choices = [(_option['id'], _option['value']) \
                        for _option in _options]

    

def get_form_instructions_json(instructions, instance):
    ''' This function will read through the RDF defined info and proccess the
        json to retrun the correct instructions for the specified form
        instance.'''

    _rdf_app = rdfw().app
    #print("inst------", instructions)
# get form instance info
    _form_instance_info = {}
    _form_instance_type_list = make_list(instructions.get('kds_formInstance', []))
    for _form_instance in _form_instance_type_list:
        if _form_instance.get('kds_formInstanceType') == instance:
            _form_instance_info = _form_instance
    _new_instr = {}
    #print("------", _form_instance_info)
#Determine the form paramaters
    _new_instr['kds_formTitle'] = _form_instance_info.get('kds_formTitle', \
            instructions.get("kds_formTitle", ""))
    _new_instr['kds_formDescription'] = _form_instance_info.get('kds_formDescription', \
            instructions.get("kds_formDescription", ""))
    _new_instr['kds_form_Method'] = _form_instance_info.get('kds_form_Method', \
            instructions.get("kds_form_Method", ""))
    _new_instr['kds_form_enctype'] = _form_instance_info.get('kds_form_enctype', \
            instructions.get("kds_form_enctype", ""))
    _new_instr['kds_propertyAddOnCss'] = _form_instance_info.get('kds_propertyAddOnCss', \
            instructions.get("kds_propertyAddOnCss", ""))
    _new_instr['kds_lookupClassUri'] = _form_instance_info.get('kds_lookupClassUri', \
            instructions.get("kds_lookupClassUri", ""))
    _new_instr['kds_lookupPropertyUri'] =\
            _form_instance_info.get('kds_lookupPropertyUri',\
                    instructions.get("kds_lookupPropertyUri", ""))
    _new_instr['kds_submitSuccessRedirect'] = \
            _form_instance_info.get('kds_submitSuccessRedirect',
                                    instructions.get(\
                                            "kds_submitSuccessRedirect", ""))
    _new_instr['kds_submitFailRedirect'] = \
            _form_instance_info.get('kds_submitFailRedirect',
                                    instructions.get("kds_submitFailRedirect", ""))

# Determine css classes
    #form row css
    css = _form_instance_info.get('kds_rowOverideCss', instructions.get(\
            'kds_rowOverideCss', None))
    if css is None:
        css = _rdf_app.get('kds_formDefault', {}).get('kds_rowCss', '')
        css = css.strip() + " " + _form_instance_info.get('kds_rowAddOnCss', \
                instructions.get('kds_rowAddOnCss', ''))
        css = css.strip()
        css.strip()
    _new_instr['kds_rowCss'] = css

    #form general css
    css = _form_instance_info.get('kds_formOverideCss', instructions.get(\
            'kds_formOverideCss', None))
    if css is None:
        css = _rdf_app.get('kds_formDefault', {}).get('kds_formCss', '')
        css = css.strip() + " " + _form_instance_info.get('kds_formAddOnCss', \
                instructions.get('kds_formAddOnCss', ''))
        css = css.strip()
        css.strip()
    _new_instr['kds_formCss'] = css

    return _new_instr


def rdf_framework_form_factory(form_url, **kwargs):
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
    # find the form name and instance from the url
    _form_location = rdfw().form_exists(form_url)
    # exit factory if form does not exist
    if _form_location is False:
        return None
    _form_uri = _form_location['form_uri']
    _instance = _form_location['instance_uri']

    rdf_form = type(_form_uri, (Form, ), {})
    setattr(rdf_form, "form_uri", _form_uri)
    _app_form = rdfw().rdf_form_dict.get(_form_uri, {})
    fields = _app_form.get('kds_properties')
    instructions = get_form_instructions_json(\
            _app_form.get('kds_formInstructions'), _instance)
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
        field = get_field_json(fld, instructions, _instance, user_info)
        if field:
            field_item = get_wtform_field(field, _instance, **kwargs)
            form_field = field_item.get('fld')
            field = field_item.get('fld_json')
            if isinstance(form_field, list):
                i = 0
                for nfld in form_field:
                    #print(fld)
                    if nfld.get('kds_field'):
                        _new_field = dict.copy(field)
                        _new_field['kds_formFieldName'] = nfld['kds_fieldName']
                        _new_field['kds_formFieldOrder'] = \
                                float(_new_field['kds_formFieldOrder']) + i
                        if fld.get("doNotSave"):
                            _new_field['doNotSave'] = True
                        else:
                            _new_field['doNotSave'] = False
                        augmented_field = add_field_attributes(\
                                nfld['kds_field'],_new_field)
                        rdf_field_list.append(_new_field)
                        setattr(rdf_form, nfld['kds_fieldName'], augmented_field)
                        i += .1
            else:
                #print(field['formFieldName'], " - ", form_field)
                if form_field:
                    #print("set --- ", field)
                    augmented_field = add_field_attributes(form_field, field)
                    field['doNotSave'] = False
                    rdf_field_list.append(field)
                    setattr(rdf_form, field['kds_formFieldName'], augmented_field)
                    if hasattr(augmented_field,"frameworkField"):

                        if "subform" in form_field.frameworkField.lower():
                            _has_subobj = True
    if kwargs.get("is_subobj"):
        field = {'kds_formFieldName':'subjectUri',
                 'kds_fieldType':{'rdf_type':'ReferenceField'},
                 'kds_formLabelName':'Hidden dataSubjectUri',
                 'kds_classUri':_lookup_class_uri,
                 'kds_propUri':'subjectUri',
                 'kds_processors':[],
                 'kds_css':'form-control',
                 'editable': False,
                 'doNotSave': False}
        rdf_field_list.append(field)
        augmented_field = add_field_attributes(StringField('dataSubjectUri'),
                                               field)
        setattr(rdf_form, 'subjectUri', augmented_field)
        setattr(rdf_form, 'is_subobj', True)
    else:
        setattr(rdf_form, 'is_subobj', False)
    setattr(rdf_form, 'has_subobj', _has_subobj)
    setattr(rdf_form, 'rdf_field_list', rdf_field_list)
    setattr(rdf_form, "rdf_instructions", instructions)
    setattr(rdf_form, "instance_uri", _instance)
    setattr(rdf_form, "data_class_uri", _lookup_class_uri)
    setattr(rdf_form, "data_subject_uri", _lookup_subject_uri)
    setattr(rdf_form, "data_prop_uri", _lookup_prop_uri)
    setattr(rdf_form, "base_url", kwargs.get("base_url"))
    setattr(rdf_form, "current_url", kwargs.get("current_url"))
    #pp.pprint(rdf_form.__dict__)
    return rdf_form
    #return rdf_form
