__author__ = "Jeremy Nelson"

import urllib.parse

import requests

API_BASE = " http://api.geonames.org/"
DEFAULT_PARAMS = {
    "q": None,
    "fuzzy": 0.8
}
