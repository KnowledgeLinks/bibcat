#-------------------------------------------------------------------------------
# Name:        badges
# Purpose:     Islandora Badges Application
#
# Author:      Jeremy Nelson
#
# Created:     16/09/2014
# Copyright:   (c) Jeremy Nelson, Colorado College, Islandora Foundation 2014
# Licence:     GPLv3
#-------------------------------------------------------------------------------
__author__ = "Jeremy Nelson"
__version_info__ = ('0', '0', '1')
__version__ = '.'.join(__version_info__)

import argparse
import json
import os
import rdflib
import urllib.request

from flask import abort, Flask, g, jsonify, redirect, render_template, request
from flask import url_for
from flask_negotiate import produces
from flask_fedora_commons import Repository

schema_namespace = rdflib.Namespace("http://schema.org/")

badge_app = Flask(__name__)
badge_app.config.from_py('application.cfg', silent=True)
if not 'FEDORA_BASE_URL' in badge_app.config:
    # Default Fedora 4 running on the same server
    badge_app.config['FEDORA_BASE_URL'] = 'http://localhost:8080/'
if not 'BADGE_ISSUER_URL' in badge_app.config:
    # Sets default to the Islandora Foundation URL
    badge_app.config['BADGE_ISSUER_URL'] = 'http://islandora.ca/'

repository = Repository(badge_app)
project_root = os.path.abspath(os.path.dirname(__file__))


@badge_app.route("/badges/<event>/<uid>")
@badge_app.route("/badges/<event>/<uid>.json")
@produces('application/json')
def badge_assertion(event, uid):
    """Route returns individual badge assertation json or 404 error if not
    found on disk.

    Args:
        event: Badge Type (Camp, Projects, Institutions, etc.)
        uid: Unique ID of the Badge

    Returns:
        Assertion JSON of issued badge
    """

    badge_path = os.path.join(
        project_root,
        "badges",
        event,
        "{}.json".format(uid))
    if not os.path.exists(badge_class_path):
        abort(404)
    badge = json.load(open(badge_path))
    return jsonify(badge)


@badge_app.route("/badges/<event>")
@badge_app.route("/badges/<event>.json")
@produces('application/json')
def badge_class(event, name):
    """Route generates a JSON BadgeClass
    <https://github.com/mozilla/openbadges-specification/> for each Islandora
    badge.

    Args:
        event: Name of Event (Camp, Projects, Institutions, etc.)

    Returns:
        Badge Class JSON
    """
    badge_class_uri = rdflib.URIRef(
        urllib.parse.urljoin(repository.base_url,
                             "/".join(['rest', 'badges', event])))

    badge_rdf = repository.read(str(badge_class_uri))
    keywords = [str(obj) for obj in badge_rdf.objects(subject=badge_class_uri,
        predicate=schema_namespace.keywords)]
    badge_class = {
        "name": badge_rdf.value(
            subject=badge_class_uri,
            predicate=schema_namespace.name),
        "description": badge_rdf.value(
            subject=badge_class_uri,
            predicate=schema_namespace.description),
        "critera": url_for('/badges/{}/critera'.format(event)),
        "issuer": badge_app.config['BADGE_ISSUER_URL'],
        "tags": keywords
        }
    return jsonify(badge_class)

@badge_app.route("/badges/<event>/critera")
def badge_critera(event):
    """Route Generates an HTML class that displays the criteria for the badge

    Args:
        event: Name of Event (Camp, Projects, Institutions, etc.)

    Returns:
        HTML display of the Badge's critera
    """
    return ""


@badge_app.route("/")
def index():
    return render_template('index.html')

def main(host, port, debug=True):
    """Function runs the development application based on arguments passed in
    from the command-line.

    Args:
        host: Host name or IP address
        port: Port number

    """
    badge_app.run(
        host=host,
        port=int(port),
        debug=debug)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('host')
    parser.add_argument('port')
    args = parser.parse_args()
    main(args.host, args.port)
