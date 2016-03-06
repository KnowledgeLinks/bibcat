import os

from rdfframework.utilities import is_not_null, make_set, make_list, pyuri,\
        slugify, clean_iri
from rdfframework import get_framework


__author__ = "Mike Stabile, Jeremy Nelson"


def image_processor(processor, obj, prop, mode="save"):
    ''' Application formats a supplied image to the specified criteria.'''
    if mode == "save":
        #x=y
        obj['prop']['calcValue'] = False
        #obj['processedData'][obj['propUri']] = "obi_testing_image_uri"
    elif mode == "load":
        return obj
    return obj

