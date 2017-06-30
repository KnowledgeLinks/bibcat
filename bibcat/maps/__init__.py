__author__ = "Jeremy Nelson"
import pkg_resources

def get_map(map_name):
    return pkg_resources.resource_string(__name__, map_name)

    
