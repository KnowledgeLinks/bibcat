"""
Name:        badges
Purpose:     Islandora Badges Application

Author:      Jeremy Nelson
/bin/bash: 5: command not found
Created:     16/09/2014
Copyright:   (c) Jeremy Nelson, Colorado College, Islandora Foundation 2014-
Licence:     GPLv3
"""
__author__ = "Jeremy Nelson"
__license__ = "GPLv3"
__version_info__ = ('0', '1', '0')
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
import redis
import requests
import socket
import time
import urllib.request
import uuid
try:
    import lib.semantic_server.app  as semantic_server
except ImportError:
    from .lib.semantic_server import app as  semantic_server

import subprocess
import sys
try:
    from .lib.semantic_server.app import config
    from .lib.semantic_server.repository.utilities.namespaces import *
    from .lib.semantic_server.repository.resources.fedora import Resource
except (ImportError, SystemError):
    from lib.semantic_server.app import config
    from lib.semantic_server.repository.utilities.namespaces import *
    from lib.semantic_server.repository.resources.fedora import Resource


from string import Template

OB = rdflib.Namespace('http://schema.openbadges.org/')

PREFIX = """PREFIX bf: <{}>
PREFIX fedora: <{}>
PREFIX iana: <{}>
PREFIX openbadge: <{}> 
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

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.abspath(os.path.join(PROJECT_ROOT, "application.cfg")))
TRIPLESTORE_URL = CONFIG.get('BADGE', 'triplestore')
ISSUER_URI = None


CLASS_EXISTS_SPARQL = """{}
SELECT DISTINCT ?entity
WHERE {{{{
  ?entity schema:alternativeName "{{}}"^^xsd:string .
}}}}""".format(PREFIX)

CHECK_ISSUER_SPARQL = """{}
SELECT DISTINCT ?entity
WHERE {{{{
   ?entity schema:url <{{}}> .
}}}}""".format(PREFIX)

CHECK_PERSON_SPARQL = """{}
SELECT DISTINCT ?entity 
WHERE {{{{
  ?entity schema:email "{{}}"^^xsd:string .
}}}}""".format(PREFIX)

FIND_ASSERTION_SPARQL = """{}
SELECT DISTINCT *
WHERE {{{{
  ?subject openbadge:uid "{{}}"^^xsd:string .
  ?subject openbadge:recipient ?IdentityObject .
  ?subject openbadge:issuedOn ?DateTime .
  ?subject openbadge:BadgeClass ?badgeURI .
  ?badgeURI schema:alternativeName ?badgeClass .
}}}}""".format(PREFIX)


FIND_CLASS_SPARQL = """{}
SELECT DISTINCT *
WHERE {{{{
  ?class rdf:type openbadge:BadgeClass .
  ?class schema:name ?name .
  ?class schema:description ?description .
  ?class openbadge:issuer ?issuer .
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
  ?subject openbadge:uid "{{}}"^^xsd:string  .
  ?subject iana:describes ?image .
}}}}""".format(PREFIX)

FIND_KEYWORDS_SPARQL = """{}
SELECT ?keyword
WHERE {{{{
   ?subject schema:alternativeName "{{}}"^^xsd:string .
   ?subject schema:keywords ?keyword .
}}}}""".format(PREFIX)

IDENT_OBJ_SPARQL = """{}
SELECT DISTINCT *
WHERE {{{{
  <{{0}}> openbadge:identity ?identHash .
  <{{0}}> openbadge:salt ?salt .
}}}}""".format(PREFIX)

UPDATE_UID_SPARQL = """{}
INSERT DATA {{{{
    <{{}}> openbadge:uid "{{}}"^^xsd:string
}}}}""".format(PREFIX)

def default_graph():
    graph = rdflib.Graph()
    graph.namespace_manager.bind('fedora', FEDORA)
    graph.namespace_manager.bind('openbadge', OB)
    graph.namespace_manager.bind('rdf', RDF)
    graph.namespace_manager.bind('schema', SCHEMA)
    graph.namespace_manager.bind('owl', OWL)
    return graph


def bake_badge_dev(badge_uri):
    with open("E:\\2015\\open-badge-atla2015.png", "rb") as img:
        return img.read()

def bake_badge(badge_uri):
    #assert_url = 'http://beta.openbadges.org/baker?assertion={0}'.format(
    #    badge_uri)
    assert_url = 'http://backpack.openbadges.org/baker?assertion={0}'.format(
        badge_uri)
    print(assert_url)
    result = urllib.request.urlopen(assert_url)
    raw_image = result.read()
    add_image_request = urllib.request.Request(
        "/".join([repository.base_uri, "rest"]),
        data=raw_image,
        method='POST')
    result = urllib.request.urlopen(add_image_request)
    return result.read()

def generate_tmp_uri(class_='Resource'):
    return rdflib.URIRef('{}/badges/tmp/{}/{}'.format(
        CONFIG.get('BADGE', 'issuer_url'),
        class_,
        datetime.datetime.utcnow().timestamp()))

def add_get_issuer(ISSUER_URI):
    if ISSUER_URI:
        return ISSUER_URI
    issuer_url = CONFIG.get('BADGE', 'issuer_url')
    issuer_check_result = requests.post(
        TRIPLESTORE_URL,
        data={"query": CHECK_ISSUER_SPARQL.format(issuer_url),
              "format": "json"})
    if issuer_check_result.status_code < 400:
        info = issuer_check_result.json().get('results').get('bindings')
        if len(info) < 1:
            issuer_graph = default_graph()
            issuer_temp_uri = generate_tmp_uri('Organization')
            issuer_graph.add((issuer_temp_uri,
                              RDF.type,
                              SCHEMA.Organization))
            issuer_graph.add((issuer_temp_uri,
                              SCHEMA.url,
                              rdflib.URIRef(issuer_url)))
            issuer_graph.add((issuer_temp_uri,
                              SCHEMA.name,
                              rdflib.Literal(CONFIG.get('BADGE', 'issuer_name'))))
            resource = Resource(config=config) 
            resource_url = resource.__create__(rdf=issuer_graph)
            ISSUER_URI = rdflib.URIRef(resource_url)
        else:
            ISSUER_URI = rdflib.URIRef(info[0].get('entity').get('value'))
    return ISSUER_URI

ISSUER_URI = add_get_issuer(ISSUER_URI)

def add_get_participant(**kwargs):
    email = kwargs.get('email')
    if email is None:
        raise ValueError("Email cannot be none")
    identity_hash = hashlib.sha256(email.encode())
    identity_hash.update(CONFIG.get('BADGE', 'identity_salt').encode())
    email_result = requests.post(
        TRIPLESTORE_URL,
        data={"query": CHECK_PERSON_SPARQL.format(email),
              "format": "json"})
    if email_result.status_code < 400:
        info = email_result.json().get('results').get('bindings')
        if len(info) > 1:
            return info[0].get('entity').get('value')
        new_person = default_graph()
        new_person_uri = generate_tmp_uri('Person')
        new_person.add((new_person_uri,
                        RDF.type,
                        SCHEMA.Person))
        new_person.add((new_person_uri,
                        SCHEMA.email,
                        rdflib.Literal(email)))
       
        for prop in ['givenName', 'familyName', 'url']:
            if prop in kwargs:
                new_person.add((new_person,
                               getattr(SCHEMA, prop),
                               rdflib.Literal(kargs.get(prop))))
        add_person = Resource(config=config)
        person_url = add_person.__create__(rdf=new_person)
        return str(person_url)

    

review_msg = """Please review the following for the Badge Class:
---------------
Name: {}
Description: {}
Started on: {}
Ended on: {}
Keywords: {}
Critera: {}
Badge location: {}
---------------"""

def create_badge_class():
    "Function creates an badge class through a command prompt"
    while 1:
        badge_name = input("Enter badge class name >>")
        check_badge_result = requests.post(
            TRIPLESTORE_URL,
            data={"query": CLASS_EXISTS_SPARQL.format(slugify(badge_name)),
                  "format": "json"})
        if check_badge_result.status_code < 400:
            info = check_badge_result.json().get('results').get('bindings')
            if len(info) > 0:
                print("{} already exists as {}\nPlease try again".format(
                    badge_name,
                    slugify(badge_name)))
            else:
                break
    
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

    print(review_msg.format(
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
        badge_class_uri = generate_tmp_uri('BadgeClass')
        class_graph = default_graph()
        class_graph.add((badge_class_uri, RDF.type, SCHEMA.EducationalEvent))
        class_graph.add((badge_class_uri, 
                         RDF.type, 
                         OB.BadgeClass))
        class_graph.add((badge_class_uri, 
                         OB.issuer,
                         ISSUER_URI))
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

def create_identity_object(email):
    person_uri = rdflib.URIRef(add_get_participant(email=email))
    identity_graph = default_graph()
    new_identity_object = Resource(config=config)
    identity_uri = generate_tmp_uri('IdentityType')
    identity_graph.add(
        (identity_uri,
         RDF.type,
         OB.IdentityType))
    
    identity_hash = hashlib.sha256(email.encode())
    salt = CONFIG.get('BADGE', 'identity_salt')
    identity_hash.update(salt.encode())
    identity_graph.add(
        (identity_uri,
         OB.salt,
         rdflib.Literal(salt)))
    identity_graph.add(
        (identity_uri, 
         OB.identity,
         rdflib.Literal("sha256${0}".format(identity_hash.hexdigest()))))
    identity_graph.add(
        (identity_uri,
         OB.hashed,
         rdflib.Literal("true",
                        datatype=XSD.boolean)))
    return str(new_identity_object.__create__(rdf=identity_graph))



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
    event_check_result = requests.post(
        TRIPLESTORE_URL,
        data={"query": FIND_CLASS_SPARQL.format(event),
              "format": "json"})
    if event_check_result.status_code < 400:
        info = event_check_result.json().get('results').get('bindings')
        if len(info) < 1:
            raise ValueError("{} event not found".format(event))
        else:
            event_uri = rdflib.URIRef(info[0].get('class').get('value'))
    badge_assertion_graph = default_graph()
    badge_uri = generate_tmp_uri('BadgeAssertion')
    badge_assertion_graph.add((badge_uri,
                               OB.BadgeClass,
                               event_uri))
    badge_assertion_graph.add((badge_uri,
                               OB.verify,
                               OB.hosted))
    badge_assertion_graph.add((badge_uri, 
                         RDF.type, 
                         OB.Badge))
    identity_uri = rdflib.URIRef(create_identity_object(email))
    badge_assertion_graph.add(
         (badge_uri, 
          OB.recipient,
          identity_uri))  
    badge_assertion_graph.add(
        (badge_uri,
         OB.verify,
         OB.hosted))
    badge_assertion_graph.add(
        (badge_uri,
         OB.issuedOn,
         rdflib.Literal(datetime.datetime.utcnow().isoformat(),
                        datatype=XSD.dateTime)))
    new_badge = Resource(config=config)
    badge_uri = new_badge.__create__(
        rdf=badge_assertion_graph,
        binary=b'a')
    if badge_uri.endswith("fcr:metadata"):
        badge_uid = badge_uri.split("/")[-2]
    else:
        badge_uid = badge_uri.split("/")[-1]
    if not new_badge.__new_property__(
        "openbadge:uid", 
        '"{}"'.format(badge_uid),
        False):
        print("ERROR unable to save OpenBadge uid={}".format(badge_uid))
    ## Manually update triplestore
    ts_update = requests.post(
        TRIPLESTORE_URL,
        data={"update": UPDATE_UID_SPARQL.format(badge_uri, badge_uid),
              "format": "json"})
    if ts_update.status_code > 399:
        print("Error updating triplestore subject={} openbadge:uid to {}".format(
            badge_uri, badge_uid))
    badge_url = "{}/BadgeAssertion/{}".format(
        CONFIG.get('BADGE', 'badge_base_url'),
        badge_uid)
    new_badge.__replace_binary__(
        badge_uri, 
        binary=bake_badge(badge_url))
    print("Issued badge {}".format(badge_url))
    return str(badge_url)


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
        resp.status_code = falcon.HTTP_200       
 

class BadgeAssertion(object):

    def __get_identity_object__(self, uri):
        salt = None
        identity = None
        sparql = IDENT_OBJ_SPARQL.format(uri) 
        ident_result = requests.post(
            TRIPLESTORE_URL,
            data={"query": sparql,
                  "format": "json"}) 
        if ident_result.status_code > 399:
            raise falcon.HTTPInternalServerError(
                "Could not retrieve {} IdentityObject".format(uri),
                "Error:\n{}\nSPARQL={}".format(
                    ident_result.text,
                    sparql))
        bindings = ident_result.json().get('results').get('bindings')
        if len(bindings) < 1:
            return
        identity_hash = bindings[0].get('identHash').get('value') 
        salt = bindings[0].get('salt').get('value')
        return {
                 "type": "email",
                 "hashed": True,
                 "salt": salt,
                 "identity": identity_hash
        }

    def __valid_image_url__(self, uuid):
        sparql = FIND_IMAGE_SPARQL.format(uuid)
        result = requests.post(
            TRIPLESTORE_URL,
            data={"query": sparql,
                  "format": "json"})
        if result.status_code < 400:
            bindings = result.json().get('results').get('bindings')
            image_url = bindings.get('image').get('value')
            badge_result = requests.get(url)
            if len(badge_result.content) > 1:
                return url
        return False

    def on_get(self, req, resp, uuid, ext='json'):
        sparql = FIND_ASSERTION_SPARQL.format(uuid)
        #print(sparql)
        result = requests.post(TRIPLESTORE_URL,
            data={"query": sparql,
                  "format": 'json'})
        if result.status_code > 399:
            raise falcon.HTTPInternalServerError(
                "Cannot retrieve {}/{} badge".format(name, uuid),
                result.text)
        bindings = result.json().get('results').get('bindings')
##        try:
        issuedOn = dateutil.parser.parse(
            bindings[0]['DateTime']['value'])
        recipient = self.__get_identity_object__(
            bindings[0]['IdentityObject'].get('value'))

        name = bindings[0]['badgeClass'].get('value')
        
        badge_base_url = CONFIG.get('BADGE', 'badge_base_url')
        badge = {
        "uid": uuid,
        "recipient": recipient,
        "badge": "{}/BadgeClass/{}".format(
            badge_base_url, 
            name),
        #"issuedOn": int(time.mktime(issuedOn.timetuple())),
        "issuedOn": issuedOn.strftime("%Y-%m-%d"),
        "verify": {
            "type": "hosted",
            "url": "{}/BadgeClass/{}.json".format(
                        badge_base_url,
                        name)
            }
        }
        # Badge has been successfully baked and badge image 
        badge_image_url = self.__valid_image_url__(uuid)
        if badge_image_url:
            badge["image"] = badge_image_url 
##        except:
##            print("Error {}".format(sys.exc_info()))
        resp.status = falcon.HTTP_200
        if ext.startswith('json'):
            resp.body = json.dumps(badge)
        else:
            resp.body = str(badge)

class BadgeClass(object):

    def __init__(self):
        pass

    def __keywords__(self, name, ext='json'):
        sparql = FIND_KEYWORDS_SPARQL.format(name)
        result = requests.post(
            TRIPLESTORE_URL,
            data={"query": sparql,
                  "format": "json"})
        info = result.json()['results']['bindings']
        output = [] 
        for result in info:
            output.append(result.get('keyword').get('value'))
        return list(set(output))

    def on_get(self, req, resp, name, ext='json'):
        if name.endswith(ext):
            name = name.split(".{}".format(ext))[0]
        resp.status = falcon.HTTP_200
        sparql = FIND_CLASS_SPARQL.format(name)
        result = requests.post(
            TRIPLESTORE_URL,
            data={"query": sparql,
                  "format": "json"})
        if result.status_code > 399:
            raise falcon.HTTPInternalServerError(
                   "Cannot retrieve {} Badge Class".format(name),
                   result.text)
        info = result.json()['results']['bindings'][0]
        keywords = self.__keywords__(name)
        badge_base_url = CONFIG.get('BADGE', 'badge_base_url')
        badge_class_json = {
            "name": info.get('name').get('value'),
            "description": info.get('description').get('value'),
            "criteria": '{}/BadgeCriteria/{}'.format(
                           badge_base_url,
                           name),
            "image": '{}/BadgeImage/{}.png'.format(
                          badge_base_url,
                          name),
            "issuer": "{}/IssuerOrganization".format(
                          badge_base_url),
             "tags": keywords
        }
        if ext.startswith('json'):
            resp.body = json.dumps(badge_class_json)


class BadgeClassCriteria(object):

    def on_get(self, req, resp, name):
        sparql = FIND_CRITERIA_SPARQL.format(name)
        badge_result = requests.post(
            TRIPLESTORE_URL,
            data={"query": sparql,
                  "format": "json"})
        if badge_result.status_code > 399:

            raise falcon.HTTPInternalServerError(
                "Cannot retrieve {}'s criteria".format(name),
                badge_result.text)
        bindings = badge_result.json().get('results').get('bindings')
        if len(bindings) < 1:
            raise falcon.HTTPNotFound()
        name ="Criteria for {} Open Badge".format(bindings[0]['name']['value']) 
        badge_criteria = {
            "name": name,
            "educationalUse": list(set([row.get('criteria').get('value') for row in bindings]))
        }
        resp.status = falcon.HTTP_200
        resp.body = json.dumps(badge_criteria) 
        

class BadgeImage(object):

    def __image_exists__(self, name, template):
        sparql = template.format(name)
        img_exists = requests.post(
            TRIPLESTORE_URL,
            data={"query": sparql,
                  "format": "json"})
        if img_exists.status_code > 399:
            raise falcon.HTTPInternalServerError(
                "Cannot retrieve {}'s image".format(name),
                img_exists.text)
        bindings = img_exists.json()['results']['bindings']
        if len(bindings) < 1:
            return False
        return bindings[0].get('image').get('value')

    def on_get(self, req, resp, name):
        resp.content_type = 'image/png'
        img_url = self.__image_exists__(name, FIND_IMAGE_SPARQL)
        if not img_url:
            img_url = self.__image_exists__(name, FIND_CLASS_IMAGE_SPARQL)
        if not img_url:
            raise falcon.HTTPNotFound()
        img_result = requests.get(img_url)
        resp.body = img_result.content

class IssuerOrganization(object):

    def on_get(self, req, resp):
        resp.body = json.dumps({"name": CONFIG.get('BADGE', 'issuer_name'),
                                "url": CONFIG.get('BADGE', 'issuer_url')})
        
#semantic_server.api.add_route("badge/{uuid}", Badge())
semantic_server.api.add_route("/BadgeClass/{name}", BadgeClass())
#semantic_server.api.add_route("/BadgeClass/{name}.{ext}", BadgeClass())
semantic_server.api.add_route("/BadgeCriteria/{name}", BadgeClassCriteria())
semantic_server.api.add_route("/BadgeImage/{name}.png", BadgeImage())
semantic_server.api.add_route("/BadgeAssertion/{uuid}", BadgeAssertion())
semantic_server.api.add_route("/IssuerOrganization", IssuerOrganization())

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
        print("Starting REST API on port 18150")
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
