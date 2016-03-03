__author__ = "Mike Stabile, Jeremy Nelson"


import os
import re
import copy
from base64 import b64encode
import datetime
import requests
from flask import current_app, json
from jinja2 import Template, Environment, FileSystemLoader
from rdflib import Namespace, XSD
from dateutil.parser import parse


DC = Namespace("http://purl.org/dc/elements/1.1/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
DOAP = Namespace("http://usefulinc.com/ns/doap#")
FOAF = Namespace("http://xmlns.com/foaf/spec/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
DEBUG = True

FRAMEWORK_BASE = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
JSON_LOCATION = os.path.join(FRAMEWORK_BASE, "json-definitions")

ENV = Environment(loader=FileSystemLoader(
    [os.path.join(FRAMEWORK_BASE, "sparql"),
     os.path.join(FRAMEWORK_BASE, "turtle")]))


def render_without_request(template_name, **template_vars):
    """
    Usage is the same as flask.render_template:

    render_without_request('my_template.html', var1='foo', var2='bar')
    """
    template = ENV.get_template(template_name)
    return template.render(**template_vars)
    

def cbool(value):
    ''' converts a value to true or false. Python's default bool() function
    does not handle 'true' of 'false' strings '''
    
    if is_not_null(value):
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            if value.lower() in ['true', '1', 't', 'y', 'yes', 'yeah', 'yup', \
                    'certainly', 'uh-huh']:
                return True
            elif value.lower() in ['false', '0', 'n', 'no']:
                return False
            else:
                return None
    else:
        return None


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


    
def fw_config(**kwargs):
    ''' function returns the application configuration information '''
    global FRAMEWORK_CONFIG
    try:
        FRAMEWORK_CONFIG
    except NameError:
        FRAMEWORK_CONFIG = None
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
            print("framework not initialized")
            return "framework not initialized"
    return FRAMEWORK_CONFIG

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

def xsd_to_python(value, data_type, rdf_type="literal", output="python"):
    ''' This will take a value and xsd data_type and convert it to a python
        variable'''
    from rdfframework import get_framework as rdfw
    if data_type:
        data_type = data_type.replace(str(XSD), "")
    if not value:
        return value
    elif rdf_type == "uri":
        return iri(value)
    elif not is_not_null(value):
        return value
    elif data_type == "xsd_anyURI":
        # URI (Uniform Resource Identifier)
        return value
    elif data_type == "xsd_base64Binary":
        # Binary content coded as "base64"
        return value.decode()
    elif data_type == "xsd_boolean":
        # Boolean (true or false)
        return cbool(value)
    elif data_type == "xsd_byte":
        # Signed value of 8 bits
        return value.decode()
    elif data_type == "xsd_date":
        ## Gregorian calendar date
        _temp_value = parse(value)
        if output == "string":
            _date_format = rdfw().app['kds_dataFormats'].get(\
                    'kds_pythonDateFormat', '')
            return _temp_value.strftime(_date_format)
        elif output == "python":
            return _temp_value
    elif data_type == "xsd_dateTime":
        ## Instant of time (Gregorian calendar)
        _temp_value = parse(value)
        if output == "string":
            _date_format = rdfw().app['kds_dataFormats'].get(\
                    'kds_pythonDateTimeFormat', '')
            return _temp_value.strftime(_date_format)
        elif output == "python":
            return _temp_value
    elif data_type == "xsd_decimal":
        # Decimal numbers
        return float(value)
    elif data_type == "xsd_double":
        # IEEE 64
        return float(value)
    elif data_type == "xsd_duration":
        # Time durations
        return timedelta(milleseconds=float(value))
    elif data_type == "xsd_ENTITIES":
        # Whitespace
        return value
    elif data_type == "xsd_ENTITY":
        # Reference to an unparsed entity
        return value
    elif data_type == "xsd_float":
        # IEEE 32
        return float(value)
    elif data_type == "xsd_gDay":
        # Recurring period of time: monthly day
        return value
    elif data_type == "xsd_gMonth":
        # Recurring period of time: yearly month
        return value
    elif data_type == "xsd_gMonthDay":
        # Recurring period of time: yearly day
        return value
    elif data_type == "xsd_gYear":
        # Period of one year
        return value
    elif data_type == "xsd_gYearMonth":
        # Period of one month
        return value
    elif data_type == "xsd_hexBinary":
        # Binary contents coded in hexadecimal
        return value
    elif data_type == "xsd_ID":
        # Definition of unique identifiers
        return value
    elif data_type == "xsd_IDREF":
        # Definition of references to unique identifiers
        return value
    elif data_type == "xsd_IDREFS":
        # Definition of lists of references to unique identifiers
        return value
    elif data_type == "xsd_int":
        # 32
        return value
    elif data_type == "xsd_integer":
        # Signed integers of arbitrary length
        return int(value)
    elif data_type == "xsd_language":
        # RFC 1766 language codes
        return value
    elif data_type == "xsd_long":
        # 64
        return int(value)
    elif data_type == "xsd_Name":
        # XML 1.O name
        return value
    elif data_type == "xsd_NCName":
        # Unqualified names
        return value
    elif data_type == "xsd_negativeInteger":
        # Strictly negative integers of arbitrary length
        return abs(int(value))*-1
    elif data_type == "xsd_NMTOKEN":
        # XML 1.0 name token (NMTOKEN)
        return value
    elif data_type == "xsd_NMTOKENS":
        # List of XML 1.0 name tokens (NMTOKEN)
        return value
    elif data_type == "xsd_nonNegativeInteger":
        # Integers of arbitrary length positive or equal to zero
        return abs(int(value))
    elif data_type == "xsd_nonPositiveInteger":
        # Integers of arbitrary length negative or equal to zero
        return abs(int(value))*-1
    elif data_type == "xsd_normalizedString":
        # Whitespace
        return value
    elif data_type == "xsd_NOTATION":
        # Emulation of the XML 1.0 feature
        return value
    elif data_type == "xsd_positiveInteger":
        # Strictly positive integers of arbitrary length
        return abs(int(value))
    elif data_type == "xsd_QName":
        # Namespaces in XML
        return value
    elif data_type == "xsd_short":
        # 32
        return value
    elif data_type == "xsd_string":
        # Any string
        return value
    elif data_type == "xsd_time":
        # Point in time recurring each day
        return parse(value)
    elif data_type == "xsd_token":
        # Whitespace
        return value
    elif data_type == "xsd_unsignedByte":
        # Unsigned value of 8 bits
        return value.decode()
    elif data_type == "xsd_unsignedInt":
        # Unsigned integer of 32 bits
        return int(value)
    elif data_type == "xsd_unsignedLong":
        # Unsigned integer of 64 bits
        return int(value)
    elif data_type == "xsd_unsignedShort":
        # Unsigned integer of 16 bits
        return int(value)
    else:
        return value

def convert_spo_to_dict(data, mode="subject", option="string"):
    '''Takes the SPAQRL query results and converts them to a python Dict

    mode: subject --> groups based on subject
    '''
    if data is None:
        return None
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
                            _obj_list.append(\
                                    xsd_to_python(item['o']['value'], \
                                    item['o'].get("datatype"), \
                                    item['o']['type'],
                                    option))
                            _return_obj[_iv][_sv][_pv] = _obj_list
                        else:
                            _return_obj[_iv][_sv][_pv] = \
                                xsd_to_python(item['o']['value'], item['o'].get(\
                                        "datatype"), item['o']['type'], option)
                    else:
                        _return_obj[_iv][_sv] = {}
                        _return_obj[_iv][_sv][_pv] = \
                                xsd_to_python(item['o']['value'], item['o'].get(\
                                "datatype"), item['o']['type'], option)
                else:
                    _return_obj[_iv] = {}
                    _return_obj[_iv][_sv] = {}
                    _return_obj[_iv][_sv][_pv] = \
                            xsd_to_python(item['o']['value'], item['o'].get(\
                            "datatype"), item['o']['type'], option)
                    
            # if not a list of objects
            else:
                if _return_obj.get(_sv):
                    if _return_obj[_sv].get(_pv):
                        _obj_list = make_list(\
                                _return_obj[_sv][_pv])
                        _obj_list.append(xsd_to_python(item['o']['value'], \
                                item['o'].get("datatype"), item['o']['type'], option))
                        _return_obj[_sv][_pv] = _obj_list
                    else:
                        _return_obj[_sv][_pv] = \
                            xsd_to_python(item['o']['value'], item['o'].get(\
                                    "datatype"), item['o']['type'], option)
                else:
                    _return_obj[_sv] = {}
                    _return_obj[_sv][_pv] = \
                            xsd_to_python(item['o']['value'], item['o'].get(\
                            "datatype"), item['o']['type'], option)
        if _list_obj:
            _return_list = []
            for _key, _value in _return_obj.items():
                _value[_key]["subjectUri"] = _key
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

def copy_obj(obj):
    ''' does a deepcopy of an object, but does not copy a class
        i.e. 
        x = {"key":[<classInstance1>,<classInstance2>,<classInstance3>]}
        y = copy_obj(x)
        y --> {"key":[<classInstance1>,<classInstance2>,<classInstance3>]} 
        del y['key'][0]
        y --> {"key":[<classInstance2>,<classInstance3>]} 
        x --> {"key":[<classInstance1>,<classInstance2>,<classInstance3>]}
        *** this is to overcome a dictionary object that lists with classes
            as the list items. '''
    
    if isinstance(obj, dict):
        return_obj = {}
        for key, value in obj.items():
            if isinstance(value, dict):
                return_obj[key] = copy_obj(value)
            elif isinstance(value, list):
                return_obj[key] = copy_obj(value)
            else:
                return_obj[key] = value
    elif isinstance(obj, list):
        return_obj = []
        for value in obj:
            if isinstance(value, dict):
                return_obj.append(copy_obj(value))
            elif isinstance(value, list):
                return_obj.append(copy_obj(value))
            else:
                return_obj.append(value)
    else:
        return_obj = copy.copy(obj)
    return return_obj
                