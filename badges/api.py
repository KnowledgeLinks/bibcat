__author__ = "Jeremy Nelson"

import falcon
from __init__ import BadgeClass, BadgeClassCriteria, BadgeAssertion 
from __init__ import BadgeImage, DefaultView, IssuerOrganization

api = falcon.API()

api.add_route("/", DefaultView())
api.add_route("/BadgeClass", BadgeClass())
api.add_route("/BadgeClass/{name}", BadgeClass())
api.add_route("/BadgeClass/{name}.{ext}", BadgeClass())
api.add_route("/BadgeCriteria/{name}", BadgeClassCriteria())
api.add_route("/BadgeImage/{name}.png", BadgeImage())
api.add_route("/Assertion/{uuid}", BadgeAssertion())
api.add_route("/Issuer", IssuerOrganization())
