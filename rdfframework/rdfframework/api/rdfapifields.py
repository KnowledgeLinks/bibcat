import datetime
import json
#from wtapis.fields import StringField, TextAreaField, PasswordField, \
#        BooleanField, FileField, DateField, DateTimeField, SelectField, Field,\
#        apiField, FieldList
#from wtapis.validators import InputRequired, Optional, URL
from rdfframework import RdfProperty, get_framework as rdfw
from rdfframework.processors import clean_processors
#from rdfframework.validators import get_wtapi_validators
from rdfframework.utilities import make_list, make_set, cbool, \
        calculate_default_value #, code_timer, \
from rdfframework.forms import get_field_security_access
#        fw_config, iri, is_not_null
#from rdfframework.apis.widgets import BsGridTableWidget, RepeatingSubapiWidget
DEBUG = False
def get_api_field_json(field, instructions, instance, user_info, item_permissions=None):
    '''This function will read through the RDF defined info and proccess the
	json to return the correct values for the instance, security and details'''
    if DEBUG:
        debug = True
    else:
        debug = False
    if item_permissions is None:
        item_permissions = []
    _rdf_app = rdfw().app
    instance = instance.replace(".html", "")
    # get class property info
    try:
        _class_prop = getattr(rdfw(), field.get(\
                'kds_classUri')).kds_properties.get(field.get('kds_propUri'),{})
    except:
        _class_prop = {}
    # merge the class prop attributes with the api prop

    #field = {**_class_prop, **field} 
    temp_field = _class_prop.copy()
    temp_field.update(field)
    field = temp_field

    # Determine Security Access
    _new_field = {}
    
    _access_level = get_field_security_access(field, user_info, item_permissions)
    if "acl_Read" not in _access_level:
        return None
    _new_field['accessLevel'] = _access_level
    
    # get api instance info
    _api_instance_info = {}
    _api_field_instance_type_list = make_list(field.get('kds_apiInstance', field.get(\
            'kds_apiDefault', {}).get('kds_apiInstance', [])))
    if debug: print("instance type list: ",_api_field_instance_type_list)
    if debug: print("instance: ", instance)
    for _field_instance in _api_field_instance_type_list:
        if _field_instance.get('kds_apiInstanceType') == instance:
            _api_instance_info = _field_instance
    if debug: print("instance info\n",_api_instance_info)
    # Determine the field paramaters
    _new_field['kds_apiFieldName'] = _api_instance_info.get('kds_apiFieldName', field.get(\
            "kds_apiFieldName", field.get('kds_apiDefault', {}).get(\
            'kds_apiFieldName', "")))
    _new_field['kds_fieldType'] = _api_instance_info.get('kds_fieldType', field.get(\
            'kds_fieldType', field.get('kds_apiDefault', {}).get('kds_fieldType', "")))
    if not isinstance(_new_field['kds_fieldType'], dict):
        _new_field['kds_fieldType'] = {"rdf_type":_new_field['kds_fieldType']}

    _new_field['kds_apiLabelName'] = _api_instance_info.get('kds_apiLabelName', \
            field.get("kds_apiLabelName", field.get('kds_apiDefault', {}).get(\
            'kds_apiLabelName', "")))
    _new_field['kds_apiFieldHelp'] = _api_instance_info.get('kds_apiFieldHelp', \
            field.get("apiFieldHelp", field.get('apiDefault', {}).get(\
            'kds_apiFieldHelp', "")))
    _new_field['kds_apiFieldOrder'] = _api_instance_info.get('kds_apiFieldOrder', \
            field.get("kds_apiFieldOrder", field.get('kds_apiDefault', {}).get(\
            'kds_apiFieldOrder', "")))
    _new_field['kds_apiLayoutRow'] = _api_instance_info.get('kds_apiLayoutRow', \
            field.get("kds_apiLayoutRow", field.get('kds_apiDefault', {}).get(\
            'kds_apiLayoutRow', "")))
    
    _new_field['rdfs_range'] = field.get('rdfs_range')
    _new_field['kds_defaultVal'] = _api_instance_info.get('kds_defaultVal',\
            field.get('kds_defaultVal'))
    _new_field['kds_propUri'] = field.get('kds_propUri')
    _new_field['kds_classUri'] = field.get('kds_classUri')
    _new_field['kds_returnValue'] = field.get('kds_returnValue')
    # get applicationActionList
    _new_field['kds_actionList'] = make_set(_api_instance_info.get(\
            'kds_applicationAction', set()))
    _new_field['kds_actionList'].union(make_set(field.get('kds_applicationAction', set())))
    _new_field['kds_actionList'] = list(_new_field['kds_actionList'])
    if debug: print("action List:_______________", _new_field['kds_actionList'])
    if "kdr_RemoveFromApi" in\
            _new_field['kds_actionList']:
        return None
    # get valiator list
    if field.get('kds_overrideValidation'):
        _new_field['kds_validators'] = field.get('kds_overrideValidation')
    else:
        _new_field['kds_validators'] = make_list(\
                _api_instance_info.get('kds_apiValidation', []))
        _new_field['kds_validators'] += make_list(\
                field.get('kds_apiValidation', []))
        _new_field['kds_validators'] += make_list(\
                field.get('kds_propertyValidation', []))
    # get processing list
    _new_field['kds_processors'] = make_list(_api_instance_info.get('kds_apiProcessing', []))
    _new_field['kds_processors'] += make_list(field.get('kds_apiProcessing', []))
    _new_field['kds_processors'] += make_list(field.get('kds_propertyProcessing', []))
    
    if debug:
        if field['kds_propUri'] == "schema_image":
            x=1
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

    return _new_field
    
def get_api_field(field, instance='', **kwargs):
    ''' return an API field '''
    if DEBUG: debug = True
    else: debug = False
    _api_field = RdfProperty(field)
    _api_field.default_value = calculate_default_value(field)
    
    if debug: print("--_api_field: ", _api_field)
    return {"fld": _api_field, "fld_json": field, "api_js": None}
    

        

    
