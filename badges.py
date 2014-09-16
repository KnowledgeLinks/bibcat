#-------------------------------------------------------------------------------
# Name:        badges
# Purpose:     Islandora Badges Application
#
# Author:      Jeremy Nelson
#
# Created:     16/09/2014
# Copyright:   (c) Jeremy Nelson, Colorado College, Islandora Foundation 2014
# Licence:     <your licence>
#-------------------------------------------------------------------------------
__author__ = "Jeremy Nelson"
__version_info__ = ('0', '0', '1')
__version__ = '.'.join(__version_info__)

import argparse
import json
import os
import urllib.request

from flask import abort, Flask, g, jsonify, redirect, render_template, request
from flask_negotiate import produces

badge_app = Flask(__name__)
project_root = os.path.abspath(os.path.dirname(__file__))

@badge_app.route("/badges/<badge_type>/<name>/<uid>")
@badge_app.route("/badges/<badge_type>/<name>/<uid>.json")
@produces('application/json')
def badge_assertion(badge_type, name, uid):
    """Route returns individual badge assertation json or 404 error if not
    found on disk.

    Args:
        badge_type: Badge Type (Camp, Projects, Institutions, etc.)
        name: Name of Badge
        uid: Unique ID of the Badge

    Returns:
        Assertion JSON of issued badge
    """
    badge_path = os.path.join(
        project_root,
        "badges",
        badge_type,
        name,
        "{}.json".format(uid))
    if not os.path.exists(badge_class_path):
        abort(404)
    badge = json.load(open(badge_path))
    return jsonify(badge)


@badge_app.route("/badges/<badge_type>/<name>")
@badge_app.route("/badges/<badge_type>/<name>.json")
@produces('application/json')
def badge_class(badge_type, name):
    """Route generates a JSON BadgeClass
    <https://github.com/mozilla/openbadges-specification/> for each Islandora
    badge.

    Args:
        badge_type: Badge Type (Camp, Projects, Institutions, etc.)
        name: Name of Badge

    Returns:
        Badge Class JSON
    """
    badge_class_path = os.path.join(
        project_root,
        "badges",
        badge_type,
        "{}.json".format(name))
    if not os.path.exists(badge_class_path):
        abort(404)
    badge_class = json.load(open(badge_class_path))
    return jsonify(badge_class)

@badge_app.route("/")
def index():
    return """<a href="http://islandora.ca/"><img src="http://islandora.ca/sites/default/files/Islandora.png"
alt="Islandora"></a>
<h1><a href="http://openbadges.org/">Open Badge</a> issuer endpoint</h1>"""

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
