__author__ = "Jeremy Nelson"
import pkg_resources

def get_definition(def_name):
    return pkg_resources.resource_string(__name__, def_name)
