''' contains functions for converting objects to namespace prefixes '''
import re
__author__ = "Mike Stabile"

NS_OBJ = None

def convert_to_ns(value, ns_obj=None):
    ''' converts a value to the prefixed rdf ns equivalent. If not found
        returns the value as is '''
    if ns_obj is None:
        from rdfframework import get_framework
        ns_obj = get_framework().ns_obj
    for _prefix, _ns_uri in ns_obj.items():
        if str(value).startswith(_ns_uri) or str(value).startswith("<"+_ns_uri):
            return value.replace(_ns_uri, _prefix + "_").replace(\
                    "<","").replace(">","")
    return value
    
def convert_to_uri(value, ns_obj=None):
    ''' converts a prefixed rdf ns equivalent value to its uri form. 
        If not found returns the value as is '''
    
    if ns_obj is None:
        from rdfframework import get_framework
        ns_obj=get_framework().ns_obj
    for _prefix, _ns_uri in ns_obj.items():
        if str(value).startswith(_prefix + "_") or \
                str(value).startswith("<%s_" % _prefix):
            return value.replace("%s_" % _prefix, _ns_uri)
    if str(value).lower() == "none":
        return ""
    else:
        return value
    
def create_namespace_obj(obj):
    ''' takes initial rdf application definitions and reads the namespaces '''
    global NS_OBJ
    _ns_obj = {}
    # find the section of the obj that holds the all the namespaces
    _key_string = "http://knowledgelinks.io/ns/data-structures/appNameSpace"
    for _app_section in obj.values():
        try:
            for _section_key in _app_section.keys():
                if _section_key == _key_string:
                    _ns_obj = _app_section[_section_key]
                    break
        except AttributeError:
            pass
    return_obj = {}  
    # cylce through the namespace section and add to the return obj 
    for _ns in _ns_obj:
        _prefix_key = "http://knowledgelinks.io/ns/data-structures/prefix"
        _ns_key = 'http://knowledgelinks.io/ns/data-structures/nameSpaceUri'
        return_obj[_ns.get(_prefix_key)] = _ns.get(_ns_key)
    NS_OBJ = return_obj
    return return_obj

def convert_obj_to_rdf_namespace(obj, ns_obj=None):
    ''' This function takes rdf json definitions and converts all of the
        uri strings to a ns_value format ''' 
    if ns_obj is None:
        from rdfframework import get_framework
        ns_obj = get_framework().ns_obj    
    
    if isinstance(obj, list):
        _return_list = []
        for item in obj:
            if isinstance(item, list):
                _return_list.append(convert_obj_to_rdf_namespace(item, ns_obj))
            elif isinstance(item, dict):
                _return_list.append(convert_obj_to_rdf_namespace(item, ns_obj))
            else:
                 _return_list.append(convert_to_ns(item, ns_obj))
        return _return_list
    elif isinstance(obj, dict):
        _return_obj = {}
        for key, item in obj.items():
            nkey = convert_to_ns(key, ns_obj)
            if isinstance(item, list):
                _return_obj[nkey] = convert_obj_to_rdf_namespace(item, ns_obj)
            elif isinstance(item, dict):
                _return_obj[nkey] = convert_obj_to_rdf_namespace(item, ns_obj)
            else:
                _return_obj[nkey] = convert_to_ns(item, ns_obj)
        return _return_obj
    else:
        return convert_to_ns(obj, ns_obj)
        
def pyuri(value):
    global NS_OBJ
    if NS_OBJ is None:
        from rdfframework import get_framework
        NS_OBJ=get_framework().ns_obj
    if str(value).startswith("http"):
        return convert_to_ns(value, NS_OBJ)
    else:
        _new_value = convert_to_ns(convert_to_uri(value, NS_OBJ), NS_OBJ)
        if value == _new_value:
            return value
        else:
            return None
    
def nouri(value):
    global NS_OBJ
    if NS_OBJ is None:
        from rdfframework import get_framework
        NS_OBJ=get_framework().ns_obj
    _uri = None
    if not str(value).startswith("http"):
        _uri = convert_to_uri(value, NS_OBJ)
    else:
        _uri = value
    if _uri:
        return re.sub(r"^(.*[#/])", "", str(_uri))
    else:
        return value
        
def uri(value): 
    global NS_OBJ
    if NS_OBJ is None:
        from rdfframework import get_framework
        NS_OBJ=get_framework().ns_obj
    if str(value).startswith("http"):
        return value
    else:
        return convert_to_uri(value)
           