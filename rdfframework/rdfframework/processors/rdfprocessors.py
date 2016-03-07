import os
from base64 import b64encode
from passlib.hash import sha256_crypt
from rdfframework.utilities import is_not_null, make_set, make_list, pyuri,\
        slugify, clean_iri, iri
from rdfframework import get_framework
from .imageprocessor import image_processor

__author__ = "Mike Stabile, Jeremy Nelson"

def run_processor(processor, obj, prop=None, mode="save"):
    '''runs the passed in processor and returns the saveData'''
    if isinstance(processor, dict):
        processor_type = processor.get('rdf_type')
    else: 
        processor_type = processor
    processor_type = processor_type.replace(\
            "http://knowledgelinks.io/ns/data-resources/", "kdr_")

    if processor_type == "kdr_SaltProcessor":
        return salt_processor(processor, obj, prop, mode)

    elif processor_type == "kdr_PasswordProcessor":
        return password_processor(processor, obj, prop, mode)

    elif processor_type == "kdr_CalculationProcessor":
        return calculation_processor(processor, obj, prop, mode)

    elif processor_type == "kdr_CSVstringToMultiPropertyProcessor":
        return csv_to_multi_prop_processor(processor, obj, prop, mode)

    elif processor_type == "kdr_AssertionImageBakingProcessor":
        return assert_img_baking_processor(processor, obj, prop, mode)

    elif processor_type == "kdr_EmailVerificationProcessor":
        return email_verification_processor(processor, obj, prop, mode)
    
    elif processor_type == "kdr_ImageProcessor":
        return image_processor(processor, obj, prop, mode)
    else:
        if mode == "load":
            return prop.query_data
        elif mode == "save":
            return obj
        return obj

def assert_img_baking_processor(processor, obj, prop, mode="save"):
    ''' Application sends badge image to the a badge baking service with the
        assertion.'''
    if mode == "save":
        obj['prop']['calcValue'] = True
        obj['processedData'][obj['propUri']] = "obi_testing_image_uri"
    elif mode == "load":
        return obj
    return obj

def csv_to_multi_prop_processor(processor, obj, prop=None, mode="save"):
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
        if prop.query_data is not None:
            prop.processed_data = ", ".join(prop.query_data)
            return ", ".join(prop.query_data)
        else:
            return ""
    return obj

def email_verification_processor(processor, obj, prop, mode="save"):
    ''' Application application initiates a proccess to verify the email
        address is a valid working address.'''
    if mode == "load":
        return obj
    return obj

def password_processor(processor, obj, prop, mode="save"):
    """Function handles application password actions

    Returns:
        modified passed in obj
    """
    salt_url = "kdr_SaltProcessor"
    if mode == "save":
        # find the salt property
        
        _class_uri = obj['prop'].get("classUri")
        _class_properties = getattr(get_framework(), _class_uri).kds_properties
        salt_property = None
        # find the property Uri that stores the salt value
        for _class_prop in _class_properties.values():
            _processors = clean_processors([make_list(\
                    _class_prop.get("kds_propertyProcessing",{}))])
            for _processor in _processors.values():
                if _processor.get("rdf_type") == salt_url:
                    salt_property = _class_prop.get("kds_propUri")
                    salt_processor_dict = _processor
        # if in save mode create a hashed password
        if mode == "save":
            # if the there is not a new password in the data return the obj
            if is_not_null(obj['prop']['new']) or obj['prop']['new'] != 'None':
                # if a salt has not been created call the salt processor
                if not obj['processedData'].get(salt_property):
                    obj = salt_processor(salt_processor_dict,
                                         obj, 
                                         mode,
                                         salt_property=salt_property)
                # create the hash
                salt = obj['processedData'].get(salt_property)
                _hash_value = sha256_crypt.encrypt(obj['prop']['new']+salt)
                # assign the hashed password to the processedData
                obj['processedData'][obj['propUri']] = _hash_value
                obj['prop']['calcValue'] = True
            return obj
    elif mode == "verify":
        # verify the supplied password matches the saved password
        if not len(obj.query_data) > 0:
            setattr(prop, "password_verified", False)
            return obj    
        _class_uri = prop.kds_classUri
        _class_properties = getattr(get_framework(), _class_uri).kds_properties
        salt_property = None
        # find the property Uri that stores the salt value
        for _class_prop in _class_properties.values():
            if _class_prop.get("kds_propertyProcessing") == salt_url:
                salt_property = _class_prop.get("kds_propUri")
        # find the salt value in the query_data
        salt_value = None
        for subject, props in obj.query_data.items():
            if clean_iri(props.get("rdf_type")) == _class_uri:
                salt_value = props.get(salt_property)
                hashed_password = props.get(prop.kds_propUri)
                break
        setattr(prop, "password_verified", \
            sha256_crypt.verify(prop.data + salt_value, hashed_password)) 
        return obj
    if mode == "load":
        return obj
    return obj

def salt_processor(processor, obj, prop, mode="save", **kwargs):
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
    _class_uri = obj['prop'].get("classUri")
    _class_properties = getattr(get_framework(), _class_uri).kds_properties
    password_property = None
    for _class_prop in _class_properties.values():
        if _class_prop.get("kds_propertyProcessing",{}).get("rdf_type") \
                == "kds_PasswordProcessor":
            password_property = obj['preSaveData'].get(\
                                            _class_prop.get("kds_propUri"))
    
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

def calculation_processor(processor, obj, prop, mode="save"):
    ''' Application should proccess the property according to the rules listed
        in the kds:calulation property.'''

    if mode == "save":
        calculation = processor.get('kds_calculation')
        if calculation:
            if calculation.startswith("slugify"):
                _prop_uri = calculation[calculation.find("(")+1:\
                                                        calculation.find(")")]
                _prop_uri = pyuri(_prop_uri)
                _value_to_slug = obj['processedData'].get(_prop_uri, \
                                        obj['preSaveData'].get(_prop_uri, {}\
                                            ).get('new', None))
                if is_not_null(_value_to_slug):
                    obj['processedData'][obj['propUri']] = \
                            slugify(_value_to_slug)
                    obj['prop']['calcValue'] = True
            else:
                pass
    elif mode == "load":
        _calc_type = processor.get('kds_calculationType')
        if _calc_type == "kdr_Concat":
            calculator_concat(processor, obj, prop, mode)
        elif _calc_type == "kdr_ObjectGenerator":
            calculator_object_generator(processor, obj, prop, mode)

    return obj

def clean_processors(processor_list_of_list, _class_uri=None):
    ''' some of the processors are stored as objects and need to retrun
        them as a list of string names'''
    debug = False
    _return_obj = {}
    # cycle through the each list of list of processors
    for processor_list in processor_list_of_list:
        # cylce through each processor in the list
        if isinstance(processor_list, list):
            for processor in processor_list:
                processor_to_add = None
                if isinstance(processor, dict):
                    # filter out processors that do not apply to the current 
                    # rdf_class
                    if _class_uri:
                        if processor.get("kds_appliesTo", _class_uri) == \
                                _class_uri:
                           processor_to_add = processor 
                    else:
                        processor_to_add = processor
                else:
                    processor_to_add = {"rdf_type": processor}
                # add the processor to the return_obj if it does not aleady
                # exist. This will allow for precedence of the first instance
                # of the processor
                if processor_to_add:
                    if not _return_obj.get(processor_to_add.get(\
                            "rdf_type")) and processor_to_add.get(\
                            "rdf_type") is not None :
                        if debug:
                            if "kdr_AssertionImageBakingProcessor" == \
                                    processor_to_add.get("rdf_type"):
                                x=y
                        _return_obj[processor_to_add.get(\
                                "rdf_type")] = processor
                        
    if len(_return_obj)>0:
        x=1
    return _return_obj

def calculate_value(value, obj, prop):
    if value.startswith("<<"):
        _lookup_value = _item.replace("<<","").replace(">>","")
        if "|" in _lookup_value:
            value_array = _lookup_value.split("|")
            _lookup_value = value_array[0]
            _class_uri = value_array[1]
        else:
            _class_uri = iri(prop.kds_classUri)
        _query_data = obj.query_data
        for _subject, _data in _query_data.items():
            if _class_uri in make_list(_data.get("rdf_type")):
                return _data.get(pyuri(_lookup_value))
    elif _item.startswith("!--"):
        if _item == "!--api_url":
            return_val = obj.api_url
        if _item == "!--base_url":
            return_val = obj.base_url
        if _item == "!--base_api_url":
            return_val = obj.base_api_url 
        return return_val
    else:
        return value
           
def calculator_concat(processor, obj, prop, mode="save", return_type="prop"):
    ''' Does a concatition based on the the provided args and kwargs '''
    _seperator = processor.get("kds_calculationSeparator",",")
    _calc_string = processor.get("kds_calculation")
    _concat_list = make_list(_calc_string.split(_seperator))
    for i, _item in enumerate(_concat_list):
        _concat_list[i] = calculate_value(_item, obj, prop)
    if return_type == "prop":
        prop.processed_data = "".join(_concat_list)
    else:
        return "".join(_concat_list)
     
   
def calculator_object_generator(processor, obj, prop, mode):   
    ''' returns and object of calculated values '''
    
    object_list = make_list(processor.get("kds_calculationObject")
    for _object in object_list:
        