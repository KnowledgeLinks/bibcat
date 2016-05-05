"""MARC21 to BIBFRAME 2.0 command-line ingester"""
__author__ = "Jeremy Nelson, Mike Stabile"

import click
import pymarc
import rdflib
import requests

def match_marc(record, pattern):
    """Takes a MARC21 and pattern extracted from the last element from a 
    http://marc21rdf.info/ URI

    Args:
        record:  MARC21 Record
        pattern: Pattern to match
    Returns:
        list of subfield values
    """
    field = record[pattern[1:4]]
    if field is not None:
        if field.indicators == [pattern[4], pattern[5]]:
            return field.get_subfields(pattern[6])


if __name__ == "__main__":
    print("In MARC21 to BIBFRAME 2.0")
