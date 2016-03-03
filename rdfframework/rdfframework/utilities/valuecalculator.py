import datetime
from rdfframework.utilities import iri, uri

def calculate_default_value(field):
    '''calculates the default value based on the field default input'''
    _calculation_string = field.get("kds_defaultVal", field.get("defaultVal"))
    _return_val = None
    if _calculation_string is None:
        return None
    if _calculation_string.startswith("item_class"):
        _return_val = iri(uri(field.get("kds_classUri",field.get("classUri"))))
    else: 
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