import os
from base64 import b64encode
from passlib.hash import sha256_crypt
from rdfframework.utilities import is_not_null
from rdfframework import get_framework


__author__ = "Mike Stabile, Jeremy Nelson"

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
            fw_config().get("REPOSITORY_URL"),
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

