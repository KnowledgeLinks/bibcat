__author__ = "Mike Stabile, Jeremy Nelson"

from rdfframework.utilities import fw_config


def get_framework(**kwargs):
    ''' sets an instance of the the framework as a global variable. This
        this method is then called to access that specific instance '''
    global RDF_GLOBAL
    
    fw_config(config=kwargs.get("config"))
    _reset = kwargs.get("reset")
    if _reset:
        from .framework import RdfFramework
        RDF_GLOBAL = RdfFramework()
    try:    
        RDF_GLOBAL
    except NameError:
        RDF_GLOBAL = None
    if RDF_GLOBAL is None:
        from .framework import RdfFramework
        RDF_GLOBAL = RdfFramework()
    return RDF_GLOBAL