"""
Name:        badges
Purpose:     Islandora Badges Application

Author:      Jeremy Nelson

Created:     16/09/2014
Copyright:   (c) Jeremy Nelson, Colorado College, Islandora Foundation 2014-
Licence:     GPLv3
"""
__author__ = "Jeremy Nelson"
__license__ = "GPLv3"
__version_info__ = ('0', '0', '3')
__version__ = '.'.join(__version_info__)

import argparse
import falcon
import hashlib
import json
import mimetypes
import os
import rdflib
import re
import requests
import urllib.request
import uuid
import lib.semantic_server.app  as semantic_server
import subprocess
import sys

from flask import abort, Flask, g, jsonify, redirect, render_template, request
from flask import current_app, url_for, Response
from flask_negotiate import produces

from lib.semantic_server.app import config
from lib.semantic_server.repository.utilities.namespaces import *
from lib.semantic_server.repository.resources.fedora import Resource

from string import Template

schema_namespace = SCHEMA
open_badges_namespace = rdflib.Namespace('http://schema.openbadges.org/')

badge_app = Flask(__name__)
badge_app.config.from_pyfile('application.cfg', silent=True)

PREFIX = """PREFIX fedora: <{}>
PREFIX iana: <{}>
PREFIX ob: <{}> 
PREFIX rdf: <{}>
PREFIX schema: <{}>
PREFIX xsd: <{}>""".format(FEDORA, 
                           IANA, 
                           open_badges_namespace, 
                           RDF, 
                           SCHEMA, 
                           XSD)

if not 'FEDORA_BASE_URL' in badge_app.config:
    # Default Fedora 4 running on the same server
    badge_app.config['FEDORA_BASE_URL'] = 'http://localhost:8080'
if not 'BADGE_ISSUER' in badge_app.config:
    # Sets default to the Islandora Foundation URL
    badge_app.config['BADGE_ISSUER'] = {
        'name': "Islandora Foundataion",
        'url': 'http://islandora.ca/'}
if not 'SEMANTIC_SERVER' in badge_app.config:
    badge_app.config['SEMANTIC_SERVER'] = {
        'host': 'localhost',
        'port': 18150}

TRIPLESTORE_URL = "http://{}:{}/triplestore".format(
    badge_app.config['SEMANTIC_SERVER'].get("host"),
    badge_app.config['SEMANTIC_SERVER'].get("port"))

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
CURRENT_DIR = os.path.dirname(PROJECT_ROOT)

FIND_ASSERTION_SPARQL = """{}
SELECT DISTINCT *
WHERE {{{{
  ?subject fedora:uuid "{{}}"^^xsd:string .
  ?subject ob:recipient ?IdentityObject .
  ?subject ob:issuedOn ?DateTime .
}}}}""".format(PREFIX)


FIND_CLASS_SPARQL = """{}
SELECT DISTINCT *
WHERE {{{{
  ?class rdf:type ob:BadgeClass .
  ?class schema:name ?name .
  ?class schema:description ?description .
  ?class ob:issuer ?issuer .
  ?class schema:alternativeName "{{}}"^^xsd:string .
}}}}""".format(PREFIX)

FIND_CLASS_IMAGE_SPARQL = """{}
SELECT DISTINCT ?image
WHERE {{{{
  ?subject schema:alternativeName "{{}}"^^xsd:string .
  ?subject iana:describes ?image .
}}}}""".format(PREFIX)


FIND_CRITERIA_SPARQL = """{}
SELECT ?name ?criteria
WHERE {{{{
  ?class schema:alternativeName "{{}}"^^xsd:string .
  ?class schema:educationalUse ?criteria .
  ?class schema:name ?name .
}}}}""".format(PREFIX)

FIND_IMAGE_SPARQL = """{}
SELECT DISTINCT ?image
WHERE {{{{
  ?subject fedora:uuid <{{}}> .
  ?subject iana:describes ?image .
}}}}""".format(PREFIX)


def default_graph():
    graph = rdflib.Graph()
    graph.namespace_manager.bind('fedora', FEDORA)
    graph.namespace_manager.bind('ob', open_badges_namespace)
    graph.namespace_manager.bind('rdf', RDF)
    graph.namespace_manager.bind('schema', SCHEMA)
    return graph


def start_fuseki(**kwargs):
    java_command = [
        "java",
        "-Xmx1200M",
        "-jar",
        "fuseki-server.jar",
    ]
    if kwargs.get('update', True):
        java_command.append("--update")
    java_command.append("--loc=store")
    java_command.append("/{}".format(kwargs.get('datastore', 'badges')))
    return java_command


@badge_app.route("/badges/<badge>/<uid>")
@badge_app.route("/badges/<badge>/<uid>.json")
#@produces('application/json')
def badge_assertion(badge, uid):
    """Route returns individual badge assertation json or 404 error if not
    found in the repository.

    Args:
        event: Badge Type (Camp, Projects, Institutions, etc.)
        uid: Unique ID of the Badge

    Returns:
        Assertion JSON of issued badge
    """
    result = requests.post(TRIPLESTORE_URL,
        data={"sparql": FIND_ASSERTION_SPARQL.format(uid)})
    if result.status_code > 399:
        abort(400)
    bindings = result.json().get('results').get('bindings')
    if len(bindings) < 1:
        abort(404)
    badge_graph = rdflib.Graph().parse(badge_uri)
    issuedOn = datetime.strptime(
        bindings[0]['IssuedOne']['value'],
        "%Y-%m-%dT%H:%M:%S.%f")             
    badge = {
        "uid": uid,
        "recipient": bindings[0]['recipient']['value'],
        "badge": url_for('badge_class', badge_classname=badge),
        "image": url_for('badge_image', badge=badge, uid=uid),
        "issuedOn": int(time.mktime(issuedOn.timetuple())),
        "verify": {
            "type": "hosted",
            "url": "{}.json".format(
                url_for('badge_assertion', badge=badge, uid=uid))
        }
    }
    return jsonify(badge)

@badge_app.route("/badges/<badge>.png")
@badge_app.route("/badges/<badge>/<uid>.png")
def badge_image(badge, uid=None):
    if uid is not None:
        # Specific Issued Badge
        result = requests.post(
            TRIPLESTORE_URL,
            data={"sparql": FIND_IMAGE_SPARQL.format(uid)})
    else:
        # Badge Class Image
        result = requests.post(
            TRIPLESTORE_URL,
            data={"sparql": FIND_CLASS_IMAGE_SPARQL.format(badge)})
    if result.status_code > 399:
        abort(400)
    bindings = result.json().get('results').get('bindings')
    if len(bindings) < 1:
        abort(404)       
    img_url = bindings[0]['image']['value']
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
    result = requests.post(
        TRIPLESTORE_URL,
        data={"sparql": FIND_CLASS_SPARQL.format(badge_classname)})
    if result.status_code > 399:
        abort(400)
    bindings = result.json().get('results').get('bindings')
    if len(bindings) < 1:
        abort(404)
    info = bindings[0]
    keyword_result = requests.post(
       TRIPLESTORE_URL,
       data={"sparql": """{}
SELECT DISTINCT ?keyword
WHERE {{
  ?subject schema:alternativeName "{}"^^xsd:string .
  ?subject schema:keywords ?keyword .
}}""".format(PREFIX, badge_classname)})
    keywords = []
    if keyword_result.status_code < 400:
        for row in keyword_result.json().get('results').get('bindings'):
            keywords.append(row['keyword']['value'])
    badge_class_json = {
        "name": info.get('name').get('value'),
        "description": info.get('description').get('value'),
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
    badge_result = requests.post(
        TRIPLESTORE_URL,
        data={"sparql": FIND_CRITERIA_SPARQL.format(badge)})
    if badge_result.status_code > 399:
        abort(400)
    bindings = badge_result.json().get('results').get('bindings')
    if len(bindings) < 1:
        abort(404)
    name ="Criteria for {} Open Badge".format(bindings[0]['name']['value']) 
    badge_criteria = {
        "name": name,
        "educationalUse": [row.get('criteria').get('value') for row in bindings]
    }
    return jsonify(badge_criteria)

@badge_app.route("/badges/issuer")
def badge_issuer_organization():
    "Route generates JSON for the badge issuer's organization"
    organization = {
        "name": badge_app.config.get('BADGE_ISSUER').get('name'),
        "url": badge_app.config.get('BADGE_ISSUER').get('url')
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
        badge_class_uri = rdflib.BNode()
        class_graph = default_graph()
        class_graph.add((badge_class_uri, RDF.type, SCHEMA.EducationalEvent))
        class_graph.add((badge_class_uri, 
                         RDF.type, 
                         open_badges_namespace.BadgeClass))
        class_graph.add((badge_class_uri, 
                         open_badges_namespace.issuer,
                         rdflib.URIRef(
                             badge_app.config['BADGE_ISSUER'].get('url'))))
        class_graph.add((badge_class_uri, 
                         SCHEMA.name, 
                         rdflib.Literal(badge_name)))
        class_graph.add((badge_class_uri, 
                   SCHEMA.alternativeName, 
                   rdflib.Literal(slugify(badge_name))))  
        class_graph.add((badge_class_uri, 
                         SCHEMA.description, 
                         rdflib.Literal(description)))
        class_graph.add((badge_class_uri, 
                         SCHEMA.startDate, 
                         rdflib.Literal(started_on)))
        if ended_on is not None or len(ended_on) > 0:
            class_graph.add((badge_class_uri, 
                             SCHEMA.endDate, 
                             rdflib.Literal(ended_on)))
        for keyword in keywords:
            class_graph.add((badge_class_uri,
                             SCHEMA.keywords,
                             rdflib.Literal(keyword)))
        for requirement in criteria:
            class_graph.add((badge_class_uri,
                             SCHEMA.educationalUse,
                             rdflib.Literal(requirement)))
        badge_class = Resource(config=config)
        badge_class_url = badge_class.__create__(
            rdf=class_graph,
            binary=badge_image)
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
    with badge_app.app_context():
        badge_url = current_app.url_for(
            'badge_assertion',
            event=event,
            uuid=str(badge_graph.value(
                subject=rdflib.URIRef(fedora_url),
                predicate=rdflib.URIRef(
                    'http://fedora.info/definitions/v4/repository#uuid'))))
    badge_assertion_graph = default_graph()
    badge_uri = rdflib.BNode()
    badge_assertion_graph.add((badge_uri,
                               open_badges_namespace.verify,
                               open_badges_namespace.hosted))
    identity_hash = hashlib.sha256(email)
    identity_hash.update(badge_app.config['IDENTITY_SALT'])
    badge_assertion_graph.add(
        (badge_uri, 
         open_badges_namespace.identity,
         rdflib.Literal("sha256${0}".format(identity_hash.hexdigest()))))

    raw_data = """
INSERT DATA {
  <> schema:email "$email" .
  <> openbadge:badge  <$badge_class_uri> .
  <> openbadge:identity "$sha256" .
  <> openbadge:verify openbadge:hosted .
  <> openbadge:issuedOn "$issuedOn"
}"""

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


class Services(object):

    def __init__(self):
        self.fedora_repo, self.cache = None, None

    def __start_services__(self):
        os.chdir(os.path.join(PROJECT_ROOT, "cache"))
        self.cache = subprocess.Popen(
            self.__start_cache__())
        os.chdir(os.path.join(PROJECT_ROOT, "fedora"))
        self.fedora_repo = subprocess.Popen(
            self.__start_fedora__(memory='1G'))
        print("Started Fedora on pid={} Redis cache pid={}".format(
            self.fedora_repo.pid,
            self.cache.pid))

    def __start_cache__(self):
        return [
            "./redis-server",
            "redis.conf"]
        
    def __start_fedora__(self, **kwargs):
        repo_json_file = os.path.join(PROJECT_ROOT, "fedora", "repository.json")
        print("Repo json file is {}".format(repo_json_file))
        java_command = [
            "java",
            "-jar",
            "-Dfcrepo.modeshape.configuration=file:{}".format(repo_json_file)]
        if "memory" in kwargs:
            java_command.append("-Xmx{}".format(kwargs.get("memory")))
        java_command.append(
            kwargs.get("jar-file",
                "fcrepo-webapp-4.2.0-jetty-console.jar"))
        java_command.append("--headless")
        return java_command


    def on_get(self, req, resp):
        resp.status = falcon.HTTP_200
        resp.body = json.dumps({ 'services': {
            "fedora4": self.fedora_repo.pid or None,
            "cache": self.cache.pid or None 
            }
        })

    def on_post(self, req, resp):
        if self.fedora_repo and self.cache:
            raise falcon.HTTPForbidden(
                "Services Already Running",
                "Fedora 4 and Cache already running")
        self.__start_services__()
        resp.status = falcon.HTTP_201
        resp.body = json.dumps({"services": {
            "fedora4": {"pid": self.fedora_repo.pid},
            "cache": {"pid": self.cache.pid}}})

    def on_delete(self, req, resp):
        if not self.cache and not self.fedora_repo:
            raise falcon.HTTPServiceUnavailable(
                "Cannot Delete Services",
                "Cache and Fedora 4 are not running",
                300)
        for service in [self.cache,
                        self.fedora_repo]:
            if service is not None:
                service.kill()
                
        resp.status = falcon.HTTP_200
        resp.body = json.dumps(
            {"message": "Services stopped"})

semantic_server.api.add_route("/services", Services())

def main(args):
    """Function runs the development application based on arguments passed in
    from the command-line.

    Args:
        args(argpare.ArgumentParser.args): Argument list

    """
    if args.action.startswith('serve'):
        host = args.host or '0.0.0.0'
        port = args.port or 5100
        badge_app.run(
            host=host,
            port=int(port),
            debug=True)
        semantic_server.main()
    elif args.action.startswith('start'):
        start_services()
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
        choices=['serve', 'start', 'issue', 'revoke', 'new'],
        help='Action for badge, choices: serve, issue, new, revoke')
    parser.add_argument('--host', help='Host IP address for dev server')
    parser.add_argument('--port', help='Port number for dev server')
    parser.add_argument('--email', help='Email account to issue event badge')
    parser.add_argument('--event', help='Event to issue badge')
    args = parser.parse_args()
    main(args)
