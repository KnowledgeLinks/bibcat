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
import redis
import requests
import socket
import urllib.request
import uuid
import lib.semantic_server.app  as semantic_server
import subprocess
import sys

from lib.semantic_server.app import config
from lib.semantic_server.repository.utilities.namespaces import *
from lib.semantic_server.repository.resources.fedora import Resource

from string import Template

OB = rdflib.Namespace('http://schema.openbadges.org/')

PREFIX = """PREFIX bf: <{}>
fedora: <{}>
PREFIX iana: <{}>
PREFIX ob: <{}> 
PREFIX rdf: <{}>
PREFIX schema: <{}>
PREFIX xsd: <{}>""".format(BF,
                           FEDORA, 
                           IANA, 
                           OB, 
                           RDF, 
                           SCHEMA, 
                           XSD)

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
CURRENT_DIR = os.path.dirname(PROJECT_ROOT)
TRIPLESTORE_URL = "http://localhost:8081/bigdata/sparql"

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
    graph.namespace_manager.bind('ob', OB)
    graph.namespace_manager.bind('rdf', RDF)
    graph.namespace_manager.bind('schema', SCHEMA)
    return graph


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
                         OB.BadgeClass))
        class_graph.add((badge_class_uri, 
                         OB.issuer,
                         rdflib.URIRef(
                             config.get('BADGE_ISSUER', 'url'))))
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
                               OB.verify,
                               OB.hosted))
    identity_hash = hashlib.sha256(email)
    identity_hash.update(badge_app.config['IDENTITY_SALT'])
    badge_assertion_graph.add(
        (badge_uri, 
         OB.identity,
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

class BadgeCollection(object):

    def on_get(self, req, resp):
        resp.stat       
 

class Badge(object):

    def __init__(self, ):
        self.uuid = None

    def on_get(self, req, resp, uuid=None):
        if uuid:
            self.uuid = uuid
       

class BadgeClass(object):

    def __init__(self):
        pass

    def on_get(self, req, resp, name):
        resp.status = falcon.HTTP_200
        resp.body = json.dumps(output)
        result = requests.post(
            TRIPLESTORE_URL,
            data={"query": FIND_CLASS_SPARQL.format(name)})


    def __on_get__(self):
        badge_class_json = {
            "name": self.cache.hget(name_hash, 'source'),
            "description": self.cache.hget(desc_hash, "source")
           # "critera": url_for('badge_criteria', badge=badge_classname),
           # "image": url_for('badge_image', badge=badge_classname),
           # "issuer": url_for('badge_issuer_organization'),
           # "tags": keywords
        }
        resp.body = json.dumps(badge_class_json)
         
        

#semantic_server.api.add_route("badge/{uuid}", Badge())
semantic_server.api.add_route("/badges", BadgeClass())
semantic_server.api.add_route("/badges/{name}", BadgeClass())

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
            "redis-server.exe",
            "redis.conf"]
        
    def __start_fedora__(self, **kwargs):
        repo_json_file = os.path.join(PROJECT_ROOT, "fedora", "repository.json")
        print("Repo json file is {}".format(repo_json_file))
        java_command = [
            "C:\\Users\\jernelson\\Downloads\\jdk1.8.0_45\\bin\\java.exe",
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

#semantic_server.api.add_route("/services", Services())

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
        semantic_server.main()
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
