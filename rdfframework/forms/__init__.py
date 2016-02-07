__author__ = "Mike Stabile, Jeremy Nelson"

import datetime
from wtforms.validators import InputRequired
try:
    from flask_wtf import Form
    from flask_wtf.file import FileField
except ImportError:
    from wtforms import Form

from wtforms.fields import StringField, TextAreaField, PasswordField, \
        BooleanField, FileField, DateField, DateTimeField, SelectField, Field,\
        FormField, FieldList
from .. import cbool, make_list, make_set
from ..framework import get_framework

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
                                                         instance,
                                                         is_subform=True),
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
    _field_req_var = cbool(field.get('requiredField'))
    if (field.get('propUri') in make_list(field.get('classInfo', {}).get(\
            'primaryKey', []))) or _field_req_var:
        _required = True
    if field.get('classUri') in make_list(field.get('requiredByDomain', {})):
        _required = True
    if _field_req_var == False:
        _required = False
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
            fw_config().get('TRIPLESTORE_URL'),
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

def rdf_framework_form_factory(name, instance='', **kwargs):
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
    _has_subform = False
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
                            _has_subform = True
    _rdf_field_list = list.copy(_field_list)
    if kwargs.get("is_subform"):
        _rdf_field_list.append([{'formFieldName':'subjectUri',
                                 'formFieldType':'ReferenceField',
                                 'formLabelName':'dataSubjectUri',
                                 'classUri':_lookup_class_uri,
                                 'className':get_framework().get_class_name(\
                                            _lookup_class_uri),
                                 'propUri':'subjectUri'}])
        setattr(rdf_form, 'subjectUri', StringField('dataSubjectUri'))
    setattr(rdf_form, 'has_subform', _has_subform)                        
    setattr(rdf_form, 'rdfFormInfo', _app_form)
    setattr(rdf_form, "rdfInstructions", instructions)
    setattr(rdf_form, "rdfFieldList", _rdf_field_list)
    setattr(rdf_form, "rdfInstance", instance)
    setattr(rdf_form, "dataClassUri", _lookup_class_uri)
    setattr(rdf_form, "dataSubjectUri", _lookup_subject_uri)
    setattr(rdf_form, "dataPropUri", _lookup_prop_uri)
    #print(json.dumps(dumpable_obj(rdf_form.__dict__),indent=4))
    return rdf_form
    #return rdf_form
