"""
Name:        badges
Purpose:     Islandora Badges Application

Author:      Jeremy Nelson

Created:     16/09/2014
Copyright:   (c) Jeremy Nelson, Colorado College, Islandora Foundation 2014
Licence:     GPLv3
"""
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
from string import Template


schema_namespace = SCHEMA_ORG
open_badges_namespace = rdflib.Namespace('http://openbadges.org')

badge_app = Flask(__name__)
badge_app.config.from_pyfile('application.cfg', silent=True)
if not 'FEDORA_BASE_URL' in badge_app.config:
    # Default Fedora 4 running on the same server
    badge_app.config['FEDORA_BASE_URL'] = 'http://localhost:8080'
if not 'BADGE_ISSUER_URL' in badge_app.config:
    # Sets default to the Islandora Foundation URL
    badge_app.config['BADGE_ISSUER_URL'] = 'http://islandora.ca/'

repository = Repository(badge_app)
project_root = os.path.abspath(os.path.dirname(__file__))

event_template = Template("""PREFIX schema: <http://schema.org/>

SELECT ?event

WHERE {
  ?event schema:name "$event" .
}""")

uuid_template = Template("""PREFIX fcrepo: <http://fedora.info/definitions/v4/repository#>

SELECT ?subject

WHERE {
  ?subject fcrepo:uuid "$uuid" .
}""")


@badge_app.route("/badges/<event>/<uid>")
@badge_app.route("/badges/<event>/<uid>.json")
@produces('application/json')
def badge_assertion(event, uid):
    """Route returns individual badge assertation json or 404 error if not
    found in the repository.

    Args:
        event: Badge Type (Camp, Projects, Institutions, etc.)
        uid: Unique ID of the Badge

    Returns:
        Assertion JSON of issued badge
    """
    badge_uri = repository.sparql(uuid_template(uuid=uid))
    if badge_uri is None:
        abort(404)
    badge_graph = rdflib.Graph().parse(badge_uri)
    badge = {


    }
    return jsonify(badge)

@badge_app.route("/badges/<event>.png")
@badge_app.route("/badges/<event>/<uid>.png")
def badge_image(event, uid=None):
    if uid is not None:
        img_url = repository.sparql(uuid_template(uuid=uid))
    else:
        img_url = repository.sparql(event_template(event=event))
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
    event_uri = repository.sparql(event_template.substitute(event=event))
    badge_rdf = rdflib.Graph().parse(event_uri)
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
    event_uri = repository.sparql(event_template(event=event))
    badge_rdf = rdflib.Graph().parse(event_uri)
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
    "Route generates JSON for the badge issuer's organization"
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
        "/".join([repository.base_uri, "rest"]),
        data=raw_image,
        method='POST')
    result = urllib.request.urlopen(add_image_request)
    return result.read()

def create_event():
    "Function creates an event through a command prompt"
    event_name = input("Enter event name >>")
    started_on = input("Event started on >>")
    ended_on = input("Event finished on >>")
    keywords = []
    while 1:
        keyword = input("Enter keyword (q to quit) >>")
        if keyword.lower() == 'q':
            break
        keywords.append(keyword)
    criteria = []
    while 1:
        requirement = input("Enter critera (q to quit) >>")
        if requirement.lower() == 'q':
            break
        criteria.append(requirement)
    print("""Please review the following for the Badge Event:
---------------
Name: {}
Started on: {}
Ended on: {}
Keywords: {}
Critera: {}
---------------""".format(
    event_name,
    started_on,
    ended_on,
    ','.join(keywords),
    ','.join(criteria)))
    prompt = input("Keep? (Y|N) >>")
    if prompt.lower() == 'y':
        template = Template("""PREFIX schema: <http://schema.org/>
PREFIX ob: <http://openbadges.org>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

INSERT DATA {
  <> rdf:type schema:EducationalEvent .
  <> schema:name "$name" .
  <> schema:startDate "$start" .
  <> schema:endDate "$end" .
  """)
        sparql = template.substitute(
            name=event_name,
            start=started_on,
            end=ended_on)
        for keyword in keywords:
            sparql += """  <> schema:keywords "{}" .\n""".format(keyword)
        for requirement in criteria:
            sparql += """  <> schema:educationalUse "{}" .\n""".format(requirement)
        sparql += "}"
        event_url = repository.create()
        update_request = urllib.request.Request(
            event_url,
            data=sparql.encode(),
            method='PATCH',
            headers={"Content-Type": "application/sparql-update"})
        result = urllib.request.urlopen(update_request)
        return event_url
    else:
        retry = input("Try again? (Y|N)")
        if retry.lower() == 'y':
            create_event()
          

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
    event_uri = repository.sparql(event_template.subsitute(event=event))
    fedora_url = repository.create()
    badge_graph = rdflib.Graph().parse(fedora_url)
    badge_url = url_for(
        'badge_assertion',
        event,
        str(badge_graph.value(
                subject=rdflib.URIref(fedora_url),
                predicate=rdflib.URIref(
                    'http://fedora.info/definitions/v4/repository#uuid'))))
    identity_hash = hashlib.sha256(email)
    identity_hash.update(badge_app.config['IDENTITY_SALT'])
    insert_template = Template("""PREFIX schema: <http://schema.org/>
PREFIX ob: <http://openbadges.org>

INSERT DATA {
  <> schema:email "$email" .
  <> schema:image <$img_url> .
  <> ob:badge  <$badge_class_uri> .
  <> ob:identity "$sha256" .
  <> ob:verify ob:hosted .
  <> ob:issuedOn "$issuedOn"
}""")
    
    sparql = insert_template.subsitute(
        email=email,
        badge_class_uri=url_for(badge_class, event),
        sha256="sha256${0}".format(identity_hash.hexdigest()),
        issuedOn=datetime.datetime.utcnow().isoformat())
    update_request = urllib.request.Request(
        fedora_url,
        method='PATCH',
        data=sparql.encode(),
        headers={"Content-Type": "application/sparql-update"})
    result = urllib.request.urlopen(update_request)
    #bake_badge(badge_uri)
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
