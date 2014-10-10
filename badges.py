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
import hashlib
import json
import os
import rdflib
import urllib.request
import uuid

from flask import abort, Flask, g, jsonify, redirect, render_template, request
from flask import url_for
from flask_negotiate import produces
from flask_fedora_commons import Repository, SCHEMA_ORG

schema_namespace = SCHEMA_ORG
open_badges_namespace = rdflib.Namespace('http://openbadges.org')

badge_app = Flask(__name__)
badge_app.config.from_pyfile('application.cfg', silent=True)
if not 'FEDORA_BASE_URL' in badge_app.config:
    # Default Fedora 4 running on the same server
    badge_app.config['FEDORA_BASE_URL'] = 'http://localhost:8080/'
if not 'BADGE_ISSUER_URL' in badge_app.config:
    # Sets default to the Islandora Foundation URL
    badge_app.config['BADGE_ISSUER_URL'] = 'http://islandora.ca/'

repository = Repository(badge_app)
project_root = os.path.abspath(os.path.dirname(__file__))

def __get_badge_class__(event):
    badge_class_uri = rdflib.URIRef(
        urllib.parse.urljoin(repository.base_url,
                             "/".join(['rest', 'badges', event])))
    return repository.read(str(badge_class_uri))

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
    badge_uri = rdflib.URIRef(
        urllib.parse.urljoin(repository.base_url,
                             "/".join(['rest', 'badges', event, uid])))
    badge = rdflib.Graph().parse(badge_uri)
    if not os.path.exists(badge_class_path):
        abort(404)
    badge = {


    }
    return jsonify(badge)

@badge_app.route("/badges/<event>.png")
@badge_app.route("/badges/<event>/<uid>.png")
def badge_image(event, uid=None):
    if uid is not None:
        img_url = urllib.parse.urljoin(repository.base_url,
            "/".join([event, uid, 'image', 'fcr:content']))
    else:
        img_url = urllib.parse.urljoin(repository.base_url,
            "/".join([event, 'image', 'fcr:content']))
    img = urllib.request.urlopen(img_url).read()
    return Response(img, mimetype='image/png')

@badge_app.route("/badges/<event>")
@badge_app.route("/badges/<event>.json")
@produces('application/json', 'application/rdf+xml', 'text/html')
def badge_class(event):
    """Route generates a JSON BadgeClass
    <https://github.com/mozilla/openbadges-specification/> for each Islandora
    badge.

    Args:
        event: Name of Event (Camp, Projects, Institutions, etc.)

    Returns:
        Badge Class JSON
    """
    badge_rdf = self.__get_badge_class__(event)
    keywords = [str(obj) for obj in badge_rdf.objects(subject=badge_class_uri,
        predicate=schema_namespace.keyword)]
    badge_class = {
        "name": badge_rdf.value(
            subject=badge_class_uri,
            predicate=schema_namespace.name),
        "description": badge_rdf.value(
            subject=badge_class_uri,
            predicate=schema_namespace.description),
        "critera": url_for('badge_criteria', event=event),
        "image": url_for('badge_image', event=event),
        "issuer": url_for('badge_issuer_organization'),
        "tags": keywords
        }
    return jsonify(badge_class)

@badge_app.route("/badges/<event>/criteria")
def badge_criteria(event):
    """Route Generates an HTML class that displays the criteria for the badge

    Args:
        event: Name of Event (Camp, Projects, Institutions, etc.)

    Returns:
        HTML display of the Badge's critera
    """
    badge_rdf = self.__get_badge_class__(event)
    badge_criteria = {
        "name": "Criteria for {}".format(
            badge_rdf.value(
                subject=badge_class_uri,
                predicate=schema_namespace.name)),
        "educationalUse": [str(obj) for obj in badge_rdf.objects(
            subject=badge_class_uri, predicate=schema_namespace.educationalUse)]
    }
    return jsonify(badge_criteria)

@badge_app.route("/badges/issuer")
def badge_issuer_organization():
    organization = {
        "name": badge_app.config['BADGE_ISSUER_NAME'],
        "url": badge_app.config['BADGE_ISSUER_URL']
    }
    return jsonify(organization)

@badge_app.route("/")
def index():
    return render_template('index.html')

def bake_badge(badge_uri):
    assert_url = 'http://beta.openbadges.org/baker?assertion={0}'.format(
        badge_uri)
    result = urllib.request.urlopen(assert_url)
    raw_image = result.read()
    add_image_request = urllib.request.Request(
        "/".join([badge_uri, 'image', 'fcr:content']),
        data=raw_image,
        method='POST')
    urllib.request.urlopen(add_image_request)


def issue_badge(email, event):
    """Function issues a badge based on an event and an email, returns the
    assertation URI.

    Args:
        email(str): Email of participant
        event(str): Event

    Returns:
        assertation_uri(str)
    """
    if email is None or event is None:
        raise ValueError("email and event cannot be None")
    badge_class = self.__get_badge_class__(event)
    badge_class_uri = rdflib.URIRef(
            urllib.parse.urljoin(repository.base_url,
                "/".join(['rest', 'badges', event])))
    identity_hash = hashlib.sha256(email)
    identity_hash.update(badge_app.config['IDENTITY_SALT'])
    badge = rdflib.Graph()
    uid = uid = str(uuid.uuid4()).split("-")[0]
    badge_uri = rdflib.URIRef(
        urllib.parse.urljoin(repository.base_url,
                             "/".join(['rest', 'badges', event, uid])))

    if repo.exists(str(badge_uri)):
        raise ValueError("{} already exists, try again".format(badge_uri))
    badge.add((
        badge_uri,
        open_badges_namespace.badge,
        badge_class_uri))
    badge.add((
        badge_uri,
        schema_namespace.email,
        rdflib.Literal(email)))
    badge.add((
        badge_uri,
        open_badges_namespace.identity,
        rdflib.Literal("sha256${0}".format(identity_hash.hexdigest()))))
    badge.add((
        badge_uri,
        open_badges_namespace.verify,
        open_badges_namespace.hosted))
    badge.add((
        badge_uri,
        open_badges_namespace.issuedOne,
        rdflib.Literal(datetime.datetime.utcnow().isoformat())))
    repo.create(str(badge_uri), badge)
    bake_badge(badge_uri)
    return str(badge_uri)

def new_badge():
    print("Add new badge for {}".format(
        badge_app.config.get('BADGE_ISSUER_NAME')))
    event = input("Event >>")
    description = input("Description >>")
    image_path = input("Path to Badge image >>")
    keywords = input("Keywords (separate by commas) >>")
    keywords = [ kw.strip() for s in keywords.split(",")]






def main(args):
    """Function runs the development application based on arguments passed in
    from the command-line.

    Args:
        args(argpare.ArgumentParser.args): Argument list

    """
    if args.action.startswith('serve'):
        host = args.host or '0.0.0.0'
        port = args.port or 5000
        badge_app.run(
            host=host,
            port=int(port),
            debug=True)
    elif args.action.startswith('issue'):
        email = args.email
        event = args.event
        issue_badge(email, event)
    elif args.action.startswith('revoke'):
        email = args.email
        event = args.event
        revoke_bade(email, event)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'action',
        choices=['serve', 'issue', 'revoke'],
        help='Action for badge, choices: serve, issue, revoke')
    parser.add_argument('--host', help='Host IP address for dev server')
    parser.add_argument('--port', help='Port number for dev server')
    parser.add_argument('--email', help='Email account to issue event badge')
    parser.add_argument('--event', help='Event to issue badge')
    args = parser.parse_args()
    main(args)
