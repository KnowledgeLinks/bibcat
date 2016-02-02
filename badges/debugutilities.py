""" utilities for debuging code """
import json
__author__ = "Mike Stabile"


def dumpable_obj(obj):
    ''' takes an object that fails with json.dumps and converts it to
    a json.dumps dumpable object. This is useful for debuging code when
    you want to dump an object for easy reading'''

    if isinstance(obj, list):
        _return_list = []
        for item in obj:
            if isinstance(item, list):
                _return_list.append(dumpable_obj(item))
            elif isinstance(item, set):
                _return_list.append(list(item))
            elif isinstance(item, dict):
                _return_list.append(dumpable_obj(item))
            else:
                try:
                    json.dumps(item)
                    _return_list.append(item)
                except:
                    _return_list.append(str(type(item)))
        return _return_list
    elif isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, dict):
        _return_obj = {}
        for key, item in obj.items():
            if isinstance(item, list):
                _return_obj[key] = dumpable_obj(item)
            elif isinstance(item, set):
                _return_obj[key] = list(item)
            elif isinstance(item, dict):
                _return_obj[key] = dumpable_obj(item)
            else:
                try:
                    json.dumps(item)
                    _return_obj[key] = item
                except:
                    _return_obj[key] = str(type(item))
        return _return_obj
    else:
        try:
            json.dumps(obj)
            return obj
        except:
            return str(type(obj))
