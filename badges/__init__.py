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

from jinja2 import Environment, FileSystemLoader, PackageLoader
from .graph import *
from .forms import NewAssertion, NewBadgeClass
from wsgiref import simple_server

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
CURRENT_DIR = os.path.dirname(PROJECT_ROOT)

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

def bake_badge_dev(badge_uri):
    with open("E:\\2015\\open-badge-atla2015.png", "rb") as img:
        return img.read()

def bake_badge(badge_uri):
    assert_url = 'http://backpack.openbadges.org/baker?assertion={0}'.format(
        badge_uri)
    result = requests.post(assert_url)
    raw_image = result.content
    return raw_image

def add_get_issuer(**kwargs):
    """Function adds or gets issuers from triplestore and returns 
    Issuer URL as a rdflib.URIRef

    Keyword Args:
        url(str): URL of Issuer
        name(str): Name of Issuer
    
    Returns
        issuer_uri(rdflib.URIRef)
    """
    url = kwargs.get('url')
    name = kwargs.get('name')
    issuer_check_result = requests.post(
        TRIPLESTORE_URL,
        data={"query": CHECK_ISSUER_SPARQL.format(url),
              "format": "json"})
    if issuer_check_result.status_code < 400:
        info = issuer_check_result.json().get('results').get('bindings')
        if len(info) < 1:
            issuer_graph = default_graph()
            new_issuer_result =  requests.post(REPOSITORY_URL)
            issuer_graph.parse(new_issuer_result.text)
            issuer_temp_uri = rdflib.URIRef(new_issuer_result.text)
            issuer_graph.add((issuer_temp_uri,
                              RDF.type,
                              SCHEMA.Organization))
            issuer_graph.add((issuer_temp_uri,
                              RDF.type,
                              OBI.Issuer))
            issuer_graph.add((issuer_temp_uri,
                              OBI.type,
                              OBI.Issuer))
            issuer_graph.add((issuer_temp_uri,
                              SCHEMA.url,
                              rdflib.URIRef(url)))
            obi_url = urllib.parse.urljoin(url, "badges/Issuer")
            issuer_graph.add((issuer_temp_uri,
                              OBI.url,
                              rdflib.URIRef(url)))
            issuer_graph.add((issuer_temp_uri,
                              OBI.name,
                              rdflib.Literal(name)))
            issuer_update_result = requests.put(str(issuer_temp_uri),
                data=issuer_graph.serialize(format='turtle'),
                headers={"Content-type": "text/turtle"})
            issuer_uri = rdflib.URIRef(str(issuer_temp_uri))
        else:
            issuer_uri = rdflib.URIRef(info[0].get('entity').get('value'))
    return issuer_uri


def add_get_participant(**kwargs):
    email = kwargs.get('email')
    if email is None:
        raise ValueError("Email cannot be none")
    email_result = requests.post(
        TRIPLESTORE_URL,
        data={"query": CHECK_PERSON_SPARQL.format(email),
              "format": "json"})
    if email_result.status_code < 400:
        info = email_result.json().get('results').get('bindings')
        if len(info) > 1:
            return rdflib.URIRef(info[0].get('entity').get('value'))
        person_response = requests.post(REPOSITORY_URL)
        if person_response.status_code > 399:
            raise falcon.HTTPBadGateway(
                description="Failed to Add Person Code {}\nError: {}".format(
                    person_response.status_code,
                    person_response.text))
        new_person_uri = rdflib.URIRef(person_response.text)
        new_person = default_graph()
        new_person.parse(str(new_person_uri))
        new_person.add((new_person_uri,
                        RDF.type,
                        SCHEMA.Person))
        new_person.add((new_person_uri,
                        SCHEMA.email,
                        rdflib.Literal(email)))
       
        for prop in ['givenName', 'familyName', 'url']:
            if prop in kwargs:
                new_person.add((new_person_uri,
                               getattr(SCHEMA, prop),
                               rdflib.Literal(kwargs.get(prop))))
        for url in kwargs.get("sameAs", []):
            new_person.add((new_person_uri,
                            rdflib.OWL.sameAs,
                            rdflib.URIRef(url)))
        update_person_response = requests.put(
            str(new_person_uri),
            data=new_person.serialize(format='turtle'),
            headers={"Content-type": "text/turtle"})
        if update_person_response.status_code > 399:
            raise falcon.HTTPBadGateway(
                title="Failed to Update {} Code {}".format(
                    new_person_uri,
                    update_person_response.status_code),
                description="Error {}".format(
                    update_person_response.text))

        return new_person_uri

    

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
        else:
            print("Error with SPARQL {}\n{}".format(check_badge_result.status_code,
                check_badge_result.text))
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
    else:
        retry = input("Try again? (Y|N)")
        if retry.lower() == 'y':
            create_badge_class()

        
def new_badge_class(**kwargs):
    """Function creates a New Badge Class using a Fedora 4 repository and
    a Blazegraph triplestore.

    Keyword arguments:
       image -- Required
       name -- Required
       description -- Required
       startDate -- Datetime in YYYY-MM-DD format, Required
       endDate -- Datetime in YYYY-MM-DD format, Optional default is None
       criteria -- List of string with each string a description criteria, 
                   good candidate for controlled vocabulary, Optional default  
                   is an empty string
       tags --  List of descriptive key-word tags, Required
       image -- Binary of Open Badge Image to be used in badge baking,
                      Required
       issuer -- Dictionary with name and url fields. Required

    Returns:
       A Python tuple of the Badge URL and the slug for the Badge
    """         
    image_raw = kwargs.get('image')
    badge_name = kwargs.get('name')
    badge_name_slug = slugify(badge_name)
    description = kwargs.get('description')
    started_on = kwargs.get('startDate')
    ended_on = kwargs.get('endDate')
    keywords = kwargs.get('tags')
    criteria = kwargs.get('criteria', None)
    issuer = kwargs.get('issuer')
    badge_image = kwargs.get('image')
    new_badge_result = requests.post(REPOSITORY_URL)
    if new_badge_result.status_code > 399:
        raise falcon.HTTPBadGateway("Error adding new badge {}\n{}".format(
	    new_badge_result.status_code,
	    new_badge_result.text))
    badge_class_uri = rdflib.URIRef(new_badge_result.text)
    image_add_response = requests.post(
        str(badge_class_uri),
        data=badge_image,
        headers={"Content-type": "image/png"})
    if image_add_response.status_code > 399:
        raise falcon.HTTPBadGateway("Error adding new badge image{}\n{}".format(
            image_add_response.status_code,
            image_add_response.text))
    image_uri = rdflib.URIRef(image_add_response.text)
    class_graph = default_graph()
    class_graph.parse(str(badge_class_uri))
    class_graph.add((badge_class_uri, RDF.type, OBI.BadgeClass))
    class_graph.add((badge_class_uri, OBI.type, OBI.BadgeClass))
    class_graph.add((badge_class_uri, RDF.type, SCHEMA.EducationalEvent))
    class_graph.add((badge_class_uri, OBI.image, image_uri))
    # Searches for issuer, creates issuer_uri
    issuer_uri = add_get_issuer(**issuer)
    class_graph.add((badge_class_uri, 
        OBI.issuer,
        issuer_uri))
    class_graph.add((badge_class_uri, 
        OBI.name, 
        rdflib.Literal(badge_name)))
    class_graph.add((badge_class_uri, 
        SCHEMA.alternativeName, 
        rdflib.Literal(badge_name_slug)))  
    class_graph.add((badge_class_uri, 
        OBI.description, 
        rdflib.Literal(description)))
    class_graph.add((badge_class_uri, 
        SCHEMA.startDate, 
        rdflib.Literal(''.join(started_on))))
    if ended_on and len(ended_on) > 0:
        class_graph.add((badge_class_uri, 
            SCHEMA.endDate, 
        rdflib.Literal(''.join(ended_on))))
    for keyword in keywords:
        class_graph.add((badge_class_uri,
            OBI.tags,
	    rdflib.Literal(keyword)))
    for requirement in criteria:
        class_graph.add((badge_class_uri,
            OBI.criteria,
            rdflib.Literal(requirement)))
    update_class_result = requests.put(
        str(badge_class_uri),
        data=class_graph.serialize(format='turtle'),
        headers={"Content-type": "text/turtle"})
    if update_class_result.status_code > 399:
        raise falcon.HTTPBadGateway("Could not update {} with RDF {}\n{} {}".format(
	    str(badge_class_uri),
	    class_graph.serialize(format='turtle').decode(),
	    update_class_result.status_code,
	    update_class_result.text))
    return str(badge_class_uri), badge_name_slug


def issue_badge(**kwargs):
    """Function issues a badge based on an event and an email, returns the
    assertation URI.

    Keyword Args:
        email(str): Email of participant
        badge(str): Badge Class 
        issuer(dict):  Dictionary with name and url fields. Required
        givenName(str): Given name of participant, defaults to None
        familyName(str): Family name of participant, defaults to None
        issuedOne(datetime): Datetime the Badge was issued, defaults to 
                             UTC timestamp

    Returns:
        assertation_uri(str)
    """
    email = kwargs.get('email')
    badge_class = kwargs.get('badge')
    issuer = kwargs.get('issuer')
    issuedOn = kwargs.get('issuedOn', datetime.datetime.utcnow())
    if email is None or badge_class is None:
        raise ValueError("email and badge class cannot be None")
    event_check_result = requests.post(
        TRIPLESTORE_URL,
        data={"query": FIND_CLASS_SPARQL.format(badge_class),
              "format": "json"})
    
    if event_check_result.status_code > 399:
        raise falcon.HTTPBadGateway(
            
            description="Could not find Badge Class Code {}\nError {}".format(
                event_check_result.status_code,
                event_check_result.text))
    info = event_check_result.json().get('results').get('bindings')
    if len(info) < 1:
        raise ValueError("{} event not found".format(event))
    else:
        event_uri = rdflib.URIRef(info[0].get('class').get('value'))
    new_assertion_response = requests.post(REPOSITORY_URL)
    if new_assertion_response.status_code > 399:
        raise falcon.HTTPBadGateway(
            description="Failed to add new Assertion Code {}\Error {}".format(
                new_assertion_response.status_code,
                new_assertion_response.text))
    badge_uri = rdflib.URIRef(new_assertion_response.text)
    badge_uid = str(badge_uri).split("/")[-1]
    badge_url = "{}/badges/Assertion/{}".format(
        issuer.get('url'),
        badge_uid)
    new_badge_img_response = requests.post(
        str(badge_uri),
        data=bake_badge_dev(badge_url),
        headers={"Content-type": 'image/png'})
    if new_badge_img_response.status_code > 399:
        raise falcon.HTTPBadGateway(
            description="Failed to add image to Assertion {} Code {}\Error {}".format(
                badge_uri,
                new_badge_img_response.status_code,
                new_badge_img_response.text))
    badge_assertion_graph = default_graph()
    badge_assertion_graph.parse(str(badge_uri))
    badge_assertion_graph.add((badge_uri,
                               RDF.type,
                               OBI.Assertion))
    badge_assertion_graph.add((badge_uri,
                               OBI.hasBadge, # Shouldn't this be OBI.badge?
                               event_uri))
    badge_assertion_graph.add((badge_uri,
                               OBI.type,
                               OBI.Assertion))
    badge_assertion_graph.add((badge_uri,
                               OBI.verify,
                               OBI.hosted))
    badge_assertion_graph.add((badge_uri, 
                         RDF.type, 
                         OBI.Badge))
    badge_assertion_graph.add((badge_uri,
        OBI.image,
        rdflib.URIRef(new_badge_img_response.text)))
    # Now add/get Recipient ID 
    recipient_uri = add_get_participant(**kwargs)
    # Save IdentityObject related triples to Assertion Graph
    salt = os.urandom(20)
    badge_assertion_graph.add((badge_uri,
                            OBI.salt,
                            rdflib.Literal(str(salt))))
    identity_hash = hashlib.sha256(email.encode())
    identity_hash.update(salt)
    badge_assertion_graph.add(
        (badge_uri,
         OBI.identity,
         rdflib.Literal("sha256?{}".format(identity_hash.hexdigest()))))
#    badge_assertion_graph.add(
#        (badge_uri,
#         OBI.uid,
#         rdflib.Literal(badge_uid)))
    
    badge_assertion_graph.add(
         (badge_uri, 
          OBI.recipient,
          recipient_uri))  
    badge_assertion_graph.add(
        (badge_uri,
         OBI.verify,
         OBI.hosted))
    badge_assertion_graph.add(
        (badge_uri,
         OBI.issuedOn,
         rdflib.Literal(issuedOn.timestamp())))
    update_badge_response = requests.put(
        str(badge_uri),
        data=badge_assertion_graph.serialize(format='turtle'),
        headers={"Content-type": "text/turtle"})
    if update_badge_response.status_code > 399:
         raise falcon.HTTPBadGateway(
            title="Failed to update Assertion {} Code {}".format(
                badge_uri,
                update_badge_response.status_code),
            description="\Error {}".format(
               update_badge_response.text))
    
       
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




def main(args):
    """Function runs the development application based on arguments passed in
    from the command-line.

    Args:
        args(argpare.ArgumentParser.args): Argument list

    """
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

def render_without_request(template_name, **template_vars):
    """
    Usage is the same as flask.render_template:

    render_without_request('my_template.html', var1='foo', var2='bar')
    """
    env = Environment(loader=FileSystemLoader(os.path.join(PROJECT_ROOT, "templates")))
    template = env.get_template(template_name)
    return template.render(**template_vars)


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
