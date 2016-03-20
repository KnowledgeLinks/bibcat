"""
Name:        badges
Purpose:     Islandora Badges Application is a Falcon REST API for creating 
             Open Badges using the Open Badges RDF Linked-Data specification 
             at <http://specification.openbadges.org/> 

Authors:      Jeremy Nelson, Mike Stabile
Created:     16/09/2014
Copyright:   (c) Jeremy Nelson, Colorado College, Islandora Foundation 2014-
Licence:     GPLv3
"""
__author__ = ",".join(["Jeremy Nelson", "Mike Stabile"])
__license__ = "GPLv3"
__version_info__ = ('0', '6', '0')
__version__ = '.'.join(__version_info__)

import argparse
import configparser
import datetime
import dateutil.parser
import falcon
import hashlib
import json
import mimetypes
import os
import rdflib
import re
import requests
import time
import urllib.parse

try:
    from flask_wtf import Form
except ImportError:
    from wtforms import Form
from jinja2 import Environment, FileSystemLoader, PackageLoader
from wsgiref import simple_server
from wtforms.fields import *


PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
CURRENT_DIR = os.path.dirname(PROJECT_ROOT)

global TRIPLESTORE_URL
ENV = Environment(loader=FileSystemLoader(os.path.join(PROJECT_ROOT, "templates")))
try:
    CONFIG = configparser.ConfigParser()
    CONFIG.read(os.path.abspath(os.path.join(PROJECT_ROOT, "application.cfg")))
    REPOSITORY_URL = "http://{}:{}/fedora/rest".format(
        CONFIG.get("DEFAULT", "host"),
        CONFIG.get("TOMCAT", "port"))
    TRIPLESTORE_URL = CONFIG.get('BADGE', 'triplestore')
except:
    # Sets to sensible Semantic Server Core defaults
    REPOSITORY_URL = "http://localhost:8080/fedora/rest"
    TRIPLESTORE_URL = "http://localhost:8080/bigdata/sparql"

def main(args):
    """Function runs the development application based on arguments passed in
    from the command-line.

    Args:
        args(argpare.ArgumentParser.args): Argument list

    """
    global TRIPLESTORE_URL
    TRIPLESTORE_URL = ""
    if args.action.startswith('serve'):
        from api import api
        print("Starting REST API on port 7500")
        host = args.host or '0.0.0.0'
        port = args.port or 7500
        httpd = simple_server.make_server(host, port, api)
        httpd.serve_forever()
    elif args.action.startswith('issue'):
        email = args.email
        event = args.event
        issue_badge(email, event)
    elif args.action.startswith('new'):
        create_badge_class()
    elif args.action.startswith('revoke'):
        email = args.email
        event = args.event
        revoke_badge(email, event)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'action',
        choices=['serve', 'issue', 'revoke', 'new'],
        help='Action for badge, choices: serve, issue, new, revoke')
    parser.add_argument('--host', help='Host IP address for dev server')
    parser.add_argument('--port', help='Port number for dev server')
    parser.add_argument('--email', help='Email account to issue event badge')
    parser.add_argument('--event', help='Event to issue badge')
    args = parser.parse_args()
    main(args)
