"""
Name:        badges
Purpose:     Islandora Badges Application is a Falcon REST API for creating 
             Open Badges using the Open Badges RDF Linked-Data specification 
             at <http://specification.openbadges.org/> 

Author:      Jeremy Nelson
Created:     16/09/2014
Copyright:   (c) Jeremy Nelson, Colorado College, Islandora Foundation 2014-
Licence:     GPLv3
"""
__author__ = "Jeremy Nelson"
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

from jinja2 import Environment, FileSystemLoader
from graph import *
from forms import NewAssertion, NewBadgeClass
from wsgiref import simple_server

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
CURRENT_DIR = os.path.dirname(PROJECT_ROOT)

ENV = Environment(loader=FileSystemLoader(os.path.join(PROJECT_ROOT, "templates")))

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.abspath(os.path.join(PROJECT_ROOT, "application.cfg")))
REPOSITORY_URL = "http://{}:{}/fedora/rest".format(
        CONFIG.get("DEFAULT", "host"),
        CONFIG.get("TOMCAT", "port"))
TRIPLESTORE_URL = CONFIG.get('BADGE', 'triplestore')

def bake_badge_dev(badge_uri):
    with open("E:\\2015\\open-badge-atla2015.png", "rb") as img:
        return img.read()

def bake_badge(badge_uri):
    assert_url = 'http://backpack.openbadges.org/baker?assertion={0}'.format(
        badge_uri)
    result = requests.post(assert_url)
    raw_image = result.content
    return raw_image

def add_get_issuer(ISSUER_URI, config=CONFIG):
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
            new_issuer_result =  requests.post("http://{}:{}/fedora/rest".format(
                config.get("DEFAULT", "host"),
                config.get("TOMCAT", "port")))
            issuer_graph.parse(new_issuer_result.text)
            issuer_temp_uri = rdflib.URIRef(new_issuer_result.text)
            issuer_graph.add((issuer_temp_uri,
                              RDF.type,
                              SCHEMA.Organization))
            issuer_graph.add((issuer_temp_uri,
                              RDF.type,
                              OBI.Issuer))
            issuer_graph.add((issuer_temp_uri,
                              OBI.url,
                              rdflib.URIRef(issuer_url)))
            issuer_graph.add((issuer_temp_uri,
                              OBI.name,
                              rdflib.Literal(CONFIG.get('BADGE', 'issuer_name'))))
            issuer_update_result = requests.put(str(issuer_temp_uri),
                data=issuer_graph.serialize(format='turtle'),
                headers={"Content-type": "text/turtle"})
            ISSUER_URI = rdflib.URIRef(str(issuer_temp_uri))
        else:
            ISSUER_URI = rdflib.URIRef(info[0].get('entity').get('value'))
    return ISSUER_URI

ISSUER_URI = add_get_issuer(ISSUER_URI=None)

def add_get_participant(**kwargs):
    email = kwargs.get('email')
    if email is None:
        raise ValueError("Email cannot be none")
    for key, val in kwargs.items():
        print(key, val, type(val))
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
                new_person.add((new_person,
                               getattr(SCHEMA, prop),
                               rdflib.Literal(kwargs.get(prop))))
        for url in kwargs.get("sameAs", []):
            new_person.add((new_person,
                            rdflib.OWL.sameAs,
                            rdflib.URIRef(url)))
        update_person_response = requests.put(
            REPOSITORY_URL,
            data=new_person.serialize(format='turtle'),
            headers={"Content-type": "text/turtle"})
        if update_person_response.status_code > 399:
            raise falcon.HTTPBadGateway(
                description="Failed to Update {} Code {}\nError {}".format(
                    new_person_uri,
                    update_person_response.status_code,
                    update_person_response.text))
        return str(person_uri)

    

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
       endDate -- Datetime in YYYY-MM-DD format, Optional default is startDate
       criteria -- List of string with each string a description criteria, 
                   good candidate for controlled vocabulary, Optional default  
                   is an empty string
       tags --  List of descriptive key-word tags, Required
       badge_image -- Binary of Open Badge Image to be used in badge baking,
                      Required

    Returns:
       A Python tuple of the Badge URL and the slug for the Badge
    """         
    image_raw = kwargs.get('image')
    badge_name = kwargs.get('name')
    badge_name_slug = slugify(badge_name)
    description = kwargs.get('description')
    started_on = kwargs.get('startDate')
    ended_on = kwargs.get('endDate', started_on)
    keywords = kwargs.get('tags')
    criteria = kwargs.get('criteria', None)
    badge_image = kwargs.get('image_file')
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
    class_graph.add((badge_class_uri, RDF.type, SCHEMA.EducationalEvent))
    class_graph.add((badge_class_uri, OBI.image, image_uri))
    class_graph.add((badge_class_uri, 
        OBI.issuer,
        ISSUER_URI))
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
        rdflib.Literal(started_on)))
    if ended_on is not None or len(ended_on) > 0:
        class_graph.add((badge_class_uri, 
            SCHEMA.endDate, 
        rdflib.Literal(ended_on)))
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

def create_identity_object(email, **kwargs):
    """Function creates an identity object based on email and updates
    the Person identityObject with any optional metadata

    Args:
        email(str): Email of recipient
       
    Keyword Args:
        givenName(str): Given name for the recipient
        familyName(str): Family name for the recipient
        sameAs(list): List of URIs that the recipient is equivalent 
    
    Returns:
        URL of new Identity Object
    """
    identity_uri = rdflib.URIRef(add_get_participant(email=email))
    identity_graph = default_graph()
    identity_graph
    identity_graph.add(
        (identity_uri,
         RDF.type,
         OBI.IdentityType))
    
    identity_hash = hashlib.sha256(email.encode())
    salt = CONFIG.get('BADGE', 'identity_salt')
    identity_hash.update(salt.encode())
    identity_graph.add(
        (identity_uri,
         OBI.salt,
         rdflib.Literal(salt)))
    identity_graph.add(
        (identity_uri, 
         OBI.identity,
         rdflib.Literal("sha256${0}".format(identity_hash.hexdigest()))))
    identity_graph.add(
        (identity_uri,
         OBI.hashed,
         rdflib.Literal("true",
                        datatype=XSD.boolean)))
    
    return str(new_identity_object.__create__(rdf=identity_graph))



def issue_badge(**kwargs):
    """Function issues a badge based on an event and an email, returns the
    assertation URI.

    Keyword Args:
        email(str): Email of participant
        badge(str): Badge Class 
        givenName(str): Given name of participant, defaults to None
        familyName(str): Family name of participant, defaults to None
        issuedOne(datetime): Datetime the Badge was issued, defaults to 
                             UTC timestamp

    Returns:
        assertation_uri(str)
    """
    email = kwargs.get('email')
    badge_class = kwargs.get('badge')
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
    badge_url = "{}/Assertion/{}".format(
        CONFIG.get('BADGE', 'badge_base_url'),
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
    badge_image_uri = rdflib.URIRef(new_badge_img_response.text)
    badge_assertion_graph = default_graph()
    badge_assertion_graph.add((badge_uri,
                               OBI.BadgeClass,
                               event_uri))
    badge_assertion_graph.add((badge_uri,
                               OBI.verify,
                               OBI.hosted))
    badge_assertion_graph.add((badge_uri, 
                         RDF.type, 
                         OBI.Badge))
    badge_assertion_graph.add((badge_uri,
        OBI.image,
        badge_image_uri))
    identity_uri = rdflib.URIRef(create_identity_object(**kwargs))
    badge_assertion_graph.add(
        (badge_uri,
         OBI.uid,
         rdflib.Literal(badge_uid)))
    badge_assertion_graph.add(
         (badge_uri, 
          OBI.recipient,
          identity_uri))  
    badge_assertion_graph.add(
        (badge_uri,
         OBI.verify,
         OBI.hosted))
    badge_assertion_graph.add(
        (badge_uri,
         OBI.issuedOn,
         rdflib.Literal(issuedOn.isoformat(),
                        datatype=XSD.dateTime)))
    update_badge_response = requests.put(
        str(badge_uri),
        data=badge_assertion_graph.serialize(format='turtle'),
        headers={"Content-type": "text/turtle"})
    if update_badge_response.status_code > 399:
         raise falcon.HTTPBadGateway(
            description="Failed to update Assertion {} Code {}\Error {}".format(
                badge_uri,
                new_assertion_response.status_code,
                new_assertion_response.text))
    
       
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

    def __html__(self):
        """Generates an Assertion Form for issuing a Badge"""
        assertion_form = NewAssertion()
        all_badges_response = requests.post(
            TRIPLESTORE_URL,
            data={"query": FIND_ALL_CLASSES,
                  "format": "json"})
        if all_badges_response.status_code > 399:
            raise falcon.HTTPBadGateway(
                description="Could not retrieve all Badge classes {}\n{}".format(
                    all_badges_response.status_code,
                    all_badges_response.text))
        bindings = all_badges_response.json().get('results').get('bindings')
        assertion_form.badge.choices = [(r.get('altName')['value'], r.get('name')['value']) for r in bindings] 
        assertion_template = ENV.get_template("assertion.html")
        return assertion_template.render(
             form=assertion_form)

    def __valid_image_url__(self, uuid):
        sparql = FIND_IMAGE_SPARQL.format(uuid)
        result = requests.post(
            TRIPLESTORE_URL,
            data={"query": sparql,
                  "format": "json"})
        if result.status_code < 400:
            bindings = result.json().get('results').get('bindings')
            if len(bindings) > 0:
                image_url = bindings[0].get('image').get('value')
                badge_result = requests.get(image_url)
                if len(badge_result.content) > 1:
                    return url
        return None

    def on_get(self, req, resp, uuid=None, ext='json'):
        if not uuid:
            resp.content_type = "text/html"
            resp.body = self.__html__()
            return
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
        "@context": "https://w3id.org/openbadges/v1",
        "uid": uuid,
        "type": "Assertion",
        "recipient": recipient,
        "badge": "{}/BadgeClass/{}".format(
            badge_base_url, 
            name),
        #"issuedOn": int(time.mktime(issuedOn.timetuple())),
        "issuedOn": issuedOn.strftime("%Y-%m-%d"),
        "verify": {
            "type": "hosted",
            "url": "{}/BadgeClass/{}".format(
                        badge_base_url,
                        name)
            }
        }
        # Badge has been successfully baked and badge image 
        badge_image_url = self.__valid_image_url__(uuid)
        print("Badge img url {}".format(badge_image_url))
        if badge_image_url:
            badge["image"] = badge_image_url 
##        except:
##            print("Error {}".format(sys.exc_info()))
        resp.status = falcon.HTTP_200
        if ext.startswith('json'):
            resp.body = json.dumps(badge)
        else:
            resp.body = str(badge)

    def on_post(self, req, resp, uuid=None, ext='json'):
        if not uuid:
            # Issue new badge
            badge_uri = issue_badge(**req.params)
            resp.status = falcon.HTTP_201
            resp.body = json.dumps({"message": "Issued Badge",
                                    "url": badge_uri})
            
        


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

    def __html__(self, name=None):
        """Generates HTML view for web-browser"""
        if not name:
            badge_class_form = NewBadgeClass()
        badge_class_template = ENV.get_template("badge_class.html")
        all_badges_response = requests.post(
            TRIPLESTORE_URL,
            data={"query": FIND_ALL_CLASSES,
                  "format": "json"})
        if all_badges_response.status_code > 399:
            raise falcon.HTTPBadGateway(
                description="Could not retrieve all Badge classes {}\n{}".format(
                    all_badges_response.status_code,
                    all_badges_response.text))
        bindings = all_badges_response.json().get('results').get('bindings')

        return badge_class_template.render(
            name=name, 
            badges=bindings,
            form=badge_class_form)

    def on_get(self, req, resp, name=None, ext='json'):
        if name and name.endswith(ext):
            name = name.split(".{}".format(ext))[0]
        resp.status = falcon.HTTP_200
        if not name:
            resp.content_type = "text/html"
            resp.body = self.__html__(name)
            return
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
            "@context": "https://w3id.org/openbadges/v1",
            "type": "BadgeClass",
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

    def on_post(self, req, resp, name=None, ext='json'):
        new_badge_url, slug_name = new_badge_class(**req.params)
        print("Slug name is {}".format(slug_name))
        resp.status = falcon.HTTP_201
        resp.body = json.dumps({"message": "Success", 
                                "url": new_badge_url,
                                "name": slug_name})
        resp.location = '/BadgeClass/{}'.format(slug_name)



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

class DefaultView(object):

    def on_get(self, req, resp):
        resp.status = falcon.HTTP_200
        resp.body = "In default view"

class IssuerOrganization(object):

    def on_get(self, req, resp):
        resp.body = json.dumps({"name": CONFIG.get('BADGE', 'issuer_name'),
                                "url": CONFIG.get('BADGE', 'issuer_url')})



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
