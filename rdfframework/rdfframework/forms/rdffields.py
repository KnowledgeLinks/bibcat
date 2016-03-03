import datetime
import json
from wtforms.fields import StringField, TextAreaField, PasswordField, \
        BooleanField, FileField, DateField, DateTimeField, SelectField, Field,\
        FormField, FieldList
from wtforms.validators import InputRequired, Optional, URL
from rdfframework import get_framework as rdfw
from rdfframework.processors import clean_processors
from rdfframework.validators import get_wtform_validators
from rdfframework.utilities import make_list, make_set, cbool, \
        calculate_default_value #, code_timer, \
#        fw_config, iri, is_not_null
from rdfframework.forms.widgets import BsGridTableWidget, RepeatingSubFormWidget

def get_field_json(field, instructions, instance, user_info, item_permissions=None):
    '''This function will read through the RDF defined info and proccess the
	json to return the correct values for the instance, security and details'''

    if item_permissions is None:
        item_permissions = []
    _rdf_app = rdfw().app
    instance = instance.replace(".html", "")
    # Determine Security Access
    _new_field = {}
    _access_level = get_field_security_access(field, user_info, item_permissions)
    if "acl_Read" not in _access_level:
        return None
    _new_field['accessLevel'] = _access_level

    # get form instance info
    _form_instance_info = {}
    _form_field_instance_type_list = make_list(field.get('kds_formInstance', field.get(\
            'kds_formDefault', {}).get('kds_formInstance', [])))
    #print("instance type list: ",_form_field_instance_type_list)
    #print("instance: ", instance)
    for _field_instance in _form_field_instance_type_list:
        if _field_instance.get('kds_formInstanceType') == instance:
            _form_instance_info = _field_instance
    #print("instance info\n",_form_instance_info)
    # Determine the field paramaters
    _new_field['kds_formFieldName'] = _form_instance_info.get('kds_formFieldName', field.get(\
            "kds_formFieldName", field.get('kds_formDefault', {}).get(\
            'kds_formFieldName', "")))
    _new_field['kds_fieldType'] = _form_instance_info.get('kds_fieldType', field.get(\
            'kds_fieldType', field.get('kds_formDefault', {}).get('kds_fieldType', "")))
    if not isinstance(_new_field['kds_fieldType'], dict):
        _new_field['kds_fieldType'] = {"rdf_type":_new_field['kds_fieldType']}

    _new_field['kds_formLabelName'] = _form_instance_info.get('kds_formLabelName', \
            field.get("kds_formLabelName", field.get('kds_formDefault', {}).get(\
            'kds_formLabelName', "")))
    _new_field['kds_formFieldHelp'] = _form_instance_info.get('kds_formFieldHelp', \
            field.get("formFieldHelp", field.get('formDefault', {}).get(\
            'kds_formFieldHelp', "")))
    _new_field['kds_formFieldOrder'] = _form_instance_info.get('kds_formFieldOrder', \
            field.get("kds_formFieldOrder", field.get('kds_formDefault', {}).get(\
            'kds_formFieldOrder', "")))
    _new_field['kds_formLayoutRow'] = _form_instance_info.get('kds_formLayoutRow', \
            field.get("kds_formLayoutRow", field.get('kds_formDefault', {}).get(\
            'kds_formLayoutRow', "")))
    _new_field['kds_propUri'] = field.get('kds_propUri')
    _new_field['kds_classUri'] = field.get('kds_classUri')
    _new_field['rdfs_range'] = field.get('rdfs_range')
    _new_field['kds_defaultVal'] = _form_instance_info.get('kds_defaultVal',\
            field.get('kds_defaultVal'))

    # get applicationActionList
    _new_field['kds_actionList'] = make_set(_form_instance_info.get(\
            'kds_applicationAction', set()))
    _new_field['kds_actionList'].union(make_set(field.get('kds_applicationAction', set())))
    _new_field['kds_actionList'] = list(_new_field['kds_actionList'])
    #print("action List:_______________", _new_field['kds_actionList'])
    if "kdr_RemoveFromForm" in\
            _new_field['kds_actionList']:
        return None
    # get valiator list
    if field.get('kds_overrideValidation'):
        _new_field['kds_validators'] = field.get('kds_overrideValidation')
    else:
        _new_field['kds_validators'] = make_list(\
                _form_instance_info.get('kds_formValidation', []))
        _new_field['kds_validators'] += make_list(\
                field.get('kds_formValidation', []))
        _new_field['kds_validators'] += make_list(\
                field.get('kds_propertyValidation', []))
    # get processing list
    _new_field['kds_processors'] = make_list(_form_instance_info.get('kds_formProcessing', []))
    _new_field['kds_processors'] += make_list(field.get('kds_formProcessing', []))
    _new_field['kds_processors'] += make_list(field.get('kds_propertyProcessing', []))

    # get required state
    _required = False
    _field_req_var = cbool(field.get('kds_requiredField'))
    if (field.get('kds_propUri') in make_list(field.get('kds_classInfo', {}).get(\
            'kds_primaryKey', []))) or _field_req_var:
        _required = True
    if field.get('kds_classUri') in make_list(field.get('kds_requiredByDomain', {})):
        _required = True
    if _field_req_var == False:
        _required = False
    _new_field['kds_required'] = _required

    # Determine EditState
    if ("acl_Write" in _access_level) and ("kdr_NotEditable" \
            not in _new_field['kds_actionList']):
        _new_field['editable'] = True
    else:
        _new_field['editable'] = False

    # Determine css classes
    css = _form_instance_info.get('kds_overideCss', field.get('kds_overideCss', \
            instructions.get('kds_overideCss', None)))
    if css is None:
        css = _rdf_app.get('kds_formDefault', {}).get('kds_fieldCss', '')
        css = css.strip() + " " + instructions.get('kds_propertyAddOnCss', '')
        css = css.strip() + " " + _form_instance_info.get('kds_addOnCss', field.get(\
                'kds_addOnCss', field.get('kds_formDefault', {}).get('kds_addOnCss', '')))
        css = css.strip()
    _new_field['kds_css'] = css
    #print("field_json:\n", json.dumps(_new_field, indent=4))

    return _new_field
    
def get_wtform_field(field, instance='', **kwargs):
    ''' return a wtform field '''
    _form_field = None
    _field_label = field.get("kds_formLabelName", '')
    #print("______label:", _field_label)
    _field_name = field.get("kds_formFieldName", '')
    _field_type_obj = field.get("kds_fieldType", {})
    if isinstance(_field_type_obj.get('rdf_type'), list):
        _field_type_obj = _field_type_obj['rdf_type'][0]
    _field_validators = get_wtform_validators(field)
    _field_type = _field_type_obj.get('rdf_type', '')
    _default_val = calculate_default_value(field)
    if _field_type == 'kdr_TextField':
        _form_field = StringField(_field_label,
                                  _field_validators,
                                  description=field.get('kds_formFieldHelp', ''))
    elif _field_type == 'kdr_ServerField':
        _form_field = None
        #form_field = StringField(_field_label, _field_validators, description= \
            #field.get('kds_formFieldHelp', ''))
    elif _field_type == 'kdr_TextAreaField':
        _form_field = TextAreaField(_field_label,
                                    _field_validators,
                                    description=field.get('kds_formFieldHelp', ''))
    elif _field_type == 'kdr_PasswordField':
        #print("!!!! Mode: ", _field_type_obj.get('fieldMode'))
        _field_mode = _field_type_obj.get('kds_fieldMode', '')
        if _field_mode == "kdr_InitialPassword":
            _form_field = [{"kds_fieldName":_field_name,
                            "kds_field":PasswordField(_field_label,
                                                  _field_validators,
                                                  description=\
                                                  field.get('kds_formFieldHelp',\
                                                         ''))},
                           {"kds_fieldName":_field_name + "_confirm",
                            "kds_field":PasswordField("Re-enter"),
                            "doNotSave":True}]

        elif _field_mode == "kdr_ChangePassword":

            _form_field = [{"kds_fieldName":_field_name + "_old",
                            "kds_field":PasswordField("Current"),
                            "doNotSave":True},
                           {"kds_fieldName":_field_name,
                            "kds_field":PasswordField("New")},
                           {"kds_fieldName":_field_name + "_confirm",
                            "kds_field":PasswordField("Re-enter"),
                            "doNotSave":True}]
        elif _field_mode == "kdr_LoginPassword":
            _form_field = PasswordField(_field_label,
                                        [InputRequired()],
                                        description=\
                                                field.get('kds_formFieldHelp', ''))
    elif _field_type == 'kdr_BooleanField':
        _form_field = BooleanField(_field_label,
                                   _field_validators,
                                   description=field.get('kds_formFieldHelp', ''))
    elif _field_type == 'kdr_FileField':
        _form_field = FileField(_field_label,
                                _field_validators,
                                description=field.get('kds_formFieldHelp', ''))
    elif _field_type == 'kdr_DateField':
        _date_format = rdfw().app.get(\
                'kds_dataFormats', {}).get('kds_pythonDateFormat', '')
        #print("date validators:\n", _field_validators)
        _add_optional = True
        for _val in _field_validators:
            if isinstance(_val, InputRequired):
                _add_optional = False
                break
        if _add_optional:
            _field_validators = [Optional()] + _field_validators

        _form_field = DateField(_field_label,
                                _field_validators,
                                description=field.get('kds_formFieldHelp', ''),
                                default=_default_val,
                                format=_date_format)
        field['kds_css'] += " dp"
    elif _field_type == 'kdr_DateTimeField':
        _form_field = DateTimeField(_field_label,
                                    _field_validators,
                                    description=field.get('kds_formFieldHelp', ''))
    elif _field_type == 'kdr_SelectField':
        #print("--Select Field: ", _field_label, _field_validators, description= \
                #field.get('kds_formFieldHelp', ''))
        _form_field = SelectField(_field_label,
                                  _field_validators,
                                  description=field.get('kds_formFieldHelp', ''))
        #_form_field = StringField(_field_label, _field_validators, description= \
                #field.get('kds_formFieldHelp', ''))
    elif _field_type == 'kdr_ImageFileOrURLField':
        _form_field = [{"kds_fieldName":_field_name +"_image",
                        "kds_field":FileField("Image File")},
                       {"kds_fieldName":_field_name + "_url",
                        "kds_field":StringField("Image Url", [URL])}]
    elif _field_type == 'kdr_SubForm':
        from .rdfforms import rdf_framework_form_factory
        _sub_form_instance = _field_type_obj.get('kds_subFormInstance',\
                                                 'kdr_LinkWithParent')
        if _sub_form_instance == 'kdr_LinkWithParent':
            _sub_form_instance = instance    
        _form_path = rdfw().get_form_path(\
                _field_type_obj.get('kds_subFormUri'), instance)
        kwargs['is_subobj'] = True
        _sub_form = FormField(\
                rdf_framework_form_factory(_form_path, is_subobj=True),
                widget=BsGridTableWidget())
        if "RepeatingSubForm" in _field_type_obj.get("kds_subFormMode"):
            _form_field = FieldList(_sub_form, _field_label, min_entries=1,
                                    widget=RepeatingSubFormWidget())
            setattr(_form_field,"frameworkField","RepeatingSubForm")
        else:
            _form_field = _sub_form
            setattr(_form_field,"frameworkField","subForm")        
    elif _field_type == 'kdr_FieldList':
        _field_json = dict.copy(field)
        _field_type_obj['rdf_type'] = _field_type_obj['kds_listFieldType']
        _field_json['kds_fieldType'] = _field_type_obj
        list_field = get_wtform_field(_field_json, instance, **kwargs)['fld']
        _form_field = FieldList(list_field, _field_label, min_entries=1)
            
    else:
        _form_field = StringField(_field_label,
                                  _field_validators,
                                  description=field.get('kds_formFieldHelp', ''))
    #print("--_form_field: ", _form_field)
    return {"fld": _form_field, "fld_json": field, "form_js": None}
    
def get_field_security_access(field, user_info, item_permissions=None):
    '''This function will return level security access allowed for the field'''
    if item_permissions is None:
        item_permissions = []
    #Check application wide access
    _app_security = user_info.get('kds_applicationSecurity', set())
    #Check class access
    _class_access_list = make_list(field.get('kds_classInfo', {"kds_classSecurity":[]}\
                ).get("kds_classSecurity", []))
    _class_access = set()
    if len(_class_access_list) > 0:
        for i in _class_access_list:
            if i['acl_agent'] in user_info['kds_userGroups']:
                _class_access.add(i.get('acl_mode'))

    #check property security
    _property_access_list = make_list(field.get('kds_propertySecurity', []))
    _property_access = set()
    if len(_property_access_list) > 0:
        for i in _property_access_list:
            if i['acl_agent'] in user_info['kds_userGroups']:
                _class_access.add(i.get('acl_mode'))

    #check item permissions
    _item_access_list = make_list(field.get('itemSecurity', []))
    _item_access = set()
    if len(_item_access_list) > 0:
        for i in _item_access_list:
            if i['agent'] in user_info['kds_userGroups']:
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
        

    
def add_field_attributes(wt_field, attributes):
    for attribute, value in attributes.items():
        setattr(wt_field, attribute, value)
    setattr(wt_field, "old_data", None)
    setattr(wt_field, "processed_data", None)
    setattr(wt_field, "query_data", None)
    return wt_field