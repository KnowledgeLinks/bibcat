"""
Name:        badges
Purpose:     Islandora Badges Application

Author:      Jeremy Nelson

Created:     16/09/2014
Copyright:   (c) Jeremy Nelson, Colorado College, Islandora Foundation 2014-
Licence:     GPLv3
"""
__author__ = "Jeremy Nelson"
__version_info__ = ('0', '0', '2')
__version__ = '.'.join(__version_info__)

import argparse
import hashlib
import json
import mimetypes
import os
import rdflib
import re
import urllib.request
import uuid
import sys


from flask import abort, Flask, g, jsonify, redirect, render_template, request
from flask import current_app, url_for
from flask_negotiate import produces
sys.path.append("C:\\Users\\jernelson\\Development\\flask-fedora")
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

badges = dict()
project_root = os.path.abspath(os.path.dirname(__file__))
repository = Repository(badge_app)

def load_badges(repository=repository):
    """Function checks for existing Fedora URL for all badges at
    {fedora_url}/rest/badges, if URL doesn't exist, creates an
    empty Fedora Object at that URL, loads all badges into a global variable.

    Args:
        repository: Fedora Repository
    """
    badges_url = "/".join(
        [badge_app.config['FEDORA_BASE_URL'],
         'rest',
         'badges'])
    if not repository.exists(badges_url):
        new_badges_request = urllib.request.Request(
            badges_url,
            method='PUT')
        response = urllib.request.urlopen(new_badges_request)
    badges_graph = rdflib.Graph().parse(badges_url)
    for obj in badges_graph.objects(
        subject=rdflib.URIRef(badges_url),
        predicate=rdflib.OWL.distinctMembers):
            badge_class_uri = rdflib.URIRef("{}/fcr:metadata".format(obj))
            badge_class_graph = rdflib.Graph().parse(str(badge_class_uri))
            badge_class_name = badge_class_graph.value(
                subject=badge_class_uri,
                predicate=schema_namespace.alternativeName)
            badges[str(badge_class_name)] = {
                'graph': badge_class_graph,
                'issued': {},
                'uri': badge_class_uri
            }




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

@badge_app.route("/badges/<badge>.png")
@badge_app.route("/badges/<badge>/<uid>.png")
def badge_image(badge, uid=None):
    if uid is not None:
        img_url = repository.sparql(uuid_template(uuid=uid))
    else:
        if not badge in badges:
            abort(404)
        img_url = '/'.join(str(badges[badge]['url']).split("/")[:-1])
    img = urllib.request.urlopen(img_url).read()
    return Response(img, mimetype='image/png')

@badge_app.route("/badges/<badge_classname>")
@badge_app.route("/badges/<badge_classname>.json")
@produces('application/json', 'application/rdf+xml', 'text/html')
def badge_class(badge_classname):
    """Route generates a JSON BadgeClass
    <https://github.com/mozilla/openbadges-specification/> for each Islandora
    badge.

    Args:
        badge_classname: Name of Badge (Camp, Projects, Institutions, etc.)

    Returns:
        Badge Class JSON
    """
    if not badge_classname in badges:
        abort(404)
    event = badges.get(badge_classname)
    badge_rdf = event.get('graph')
    badge_class_uri = event.get('uri')
    keywords = [str(obj) for obj in badge_rdf.objects(
        subject=badge_class_uri,
        predicate=schema_namespace.keywords)]
    badge_class_json = {
        "name": badge_rdf.value(
            subject=badge_class_uri,
            predicate=schema_namespace.name),
        "description": badge_rdf.value(
            subject=badge_class_uri,
            predicate=schema_namespace.description),
        "critera": url_for('badge_criteria', badge=badge_classname),
        "image": url_for('badge_image', badge=badge_classname),
        "issuer": url_for('badge_issuer_organization'),
        "tags": keywords
        }
    return jsonify(badge_class_json)

@badge_app.route("/badges/<badge>/criteria")
def badge_criteria(badge):
    """Route displays the criteria for the badge class

    Args:
        badge: Name of Badge (Camp, Projects, Institutions, etc.)

    Returns:
        JSON of badge's critera
    """
    if not badge in badges:
        abort(404)
    event = badges.get(badge)
    badge_rdf = event.get('graph')
    badge_class_uri = event.get('uri')
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

def create_badge_class():
    "Function creates an badge class through a command prompt"
    badge_name = input("Enter badge class name >>")
    description = input("Description >>")
    started_on = input("Badge started on >>")
    ended_on = input("Event finished on (can leave blank) >>")
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
    image_location = input("Enter file path or URL for badge class image >>")

    print("""Please review the following for the Badge Class:
---------------
Name: {}
Description: {}
Started on: {}
Ended on: {}
Keywords: {}
Critera: {}
Badge location: {}
---------------""".format(
    badge_name,
    description,
    started_on,
    ended_on,
    ','.join(keywords),
    ','.join(criteria),
    image_location))
    prompt = input("Keep? (Y|N) >>")
    if prompt.lower() == 'y':
        if image_location.startswith("http"):
            badge_image = urllib.request.urlopen(image_location).read()
        else:
            badge_image = open(image_location, 'rb').read()
        badge_request = urllib.request.Request(
            '/'.join([repository.base_url, 'rest']),
            data=badge_image,
            headers={"Content-Type": mimetypes.guess_type(image_location)[0]})
        result = urllib.request.urlopen(badge_request)
        badge_class_url = result.read().decode()
        template = Template("""PREFIX schema: <http://schema.org/>
PREFIX openbadge: <http://openbadges.org>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

INSERT DATA {
  <> rdf:type schema:EducationalEvent .
  <> schema:name "$name" .
  <> schema:alternativeName "$altName" .
  <> schema:description "$description" .
  <> schema:startDate "$start" .
  """)
        sparql = template.substitute(
            name=badge_name,
            altName=slugify(badge_name),
            description=description,
            start=started_on)
        if ended_on is not None or len(ended_on) > 0:
            sparql += """<> schema:endDate "{}" .\n""".format(ended_on)
        for keyword in keywords:
            sparql += """  <> schema:keywords "{}" .\n""".format(keyword)
        for requirement in criteria:
            sparql += """  <> schema:educationalUse "{}" .\n""".format(requirement)
        sparql += "}"

        update_request = urllib.request.Request(
            badge_class_url + "/fcr:metadata",
            data=sparql.encode(),
            method='PATCH',
            headers={"Content-Type": "application/sparql-update"})
        result = urllib.request.urlopen(update_request)
        repository.insert('/'.join([repository.base_url, 'rest', 'badges']),
            'owl:distinctMembers', badge_class_url)
        load_badges()
        return badge_class_url
    else:
        retry = input("Try again? (Y|N)")
        if retry.lower() == 'y':
            create_badge_class()


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
    if not event in badges:
        raise ValueError("Unknown event {}".format(event))
    event_uri = badges[event].get('uri')
    fedora_url = repository.create()
    badge_graph = rdflib.Graph().parse(fedora_url)
    with badge_app.app_context():
        badge_url = current_app.url_for(
            'badge_assertion',
            event=event,
            uuid=str(badge_graph.value(
                subject=rdflib.URIRef(fedora_url),
                predicate=rdflib.URIRef(
                    'http://fedora.info/definitions/v4/repository#uuid'))))
    identity_hash = hashlib.sha256(email)
    identity_hash.update(badge_app.config['IDENTITY_SALT'])
    insert_template = Template("""PREFIX schema: <http://schema.org/>
PREFIX openbadge: <http://openbadges.org>

INSERT DATA {
  <> schema:email "$email" .
  <> schema:image <$img_url> .
  <> openbadge:badge  <$badge_class_uri> .
  <> openbadge:identity "$sha256" .
  <> openbadge:verify openbadge:hosted .
  <> openbadge:issuedOn "$issuedOn"
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
    repository.insert("/".join([repository.base_url, 'rest', 'badges']),
        "schema:AchieveAction",
        fedora_url)
    #bake_badge(badge_uri)
    return str(badge_uri)


def slugify(value):
    """Converts to lowercase, removes non-word characters (alphanumerics and
    underscores) and converts spaces to hyphens. Also strips leading and
    trailing whitespace using Django format

    Args:

    """
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)


def main(args):
    """Function runs the development application based on arguments passed in
    from the command-line.

    Args:
        args(argpare.ArgumentParser.args): Argument list

    """
    if args.action.startswith('serve'):
        load_badges()
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
    elif args.action.startswith('new'):
        create_badge_class()
    elif args.action.startswith('revoke'):
        email = args.email
        event = args.event
        revoke_bade(email, event)


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
