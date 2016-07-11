"""Helper Class and Functions for resolving Library Linked Data Carriers"""
__author__ = "Jeremy Nelson, Mike Stabile"

from linker import Linker

class CarrierLinker(Linker):
    """Links existing Library of Congress Carrier Types to existing URL"""

    def __init__(self, **kwargs):
        super(CarrierLinker, self).__init__(**kwargs)
