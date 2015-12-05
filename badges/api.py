__author__ = "Jeremy Nelson"

import falcon
from __init__ import BadgeClass, BadgeClassCriteria, BadgeAssertion 
from __init__ import BadgeImage, DefaultView, IssuerOrganization

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
CURRENT_DIR = os.path.dirname(PROJECT_ROOT)

ENV = Environment(loader=FileSystemLoader(os.path.join(PROJECT_ROOT, "templates")))

api = falcon.API()

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


api.add_route("/", DefaultView())
api.add_route("/BadgeClass", BadgeClass())
api.add_route("/BadgeClass/{name}", BadgeClass())
api.add_route("/BadgeClass/{name}.{ext}", BadgeClass())
api.add_route("/BadgeCriteria/{name}", BadgeClassCriteria())
api.add_route("/BadgeImage/{name}.png", BadgeImage())
api.add_route("/Assertion", BadgeAssertion())
api.add_route("/Assertion/{uuid}", BadgeAssertion())
api.add_route("/Issuer", IssuerOrganization())
