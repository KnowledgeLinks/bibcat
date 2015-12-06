__author__ = "Jeremy Nelson"


import requests
from flask import abort, Blueprint, jsonify, render_template, Response, request
from flask import redirect, url_for
from flask_negotiate import produces
from . import new_badge_class
from .forms import NewBadgeClass, NewAssertion
from .graph import *
       
    

open_badge = Blueprint("open_badge", __name__,
                       template_folder="templates")
open_badge.config = {}

@open_badge.record
def record_params(setup_state):
    app = setup_state.app
    open_badge.config = dict([(key, value) for (key,value) in app.config.items()])

def get_badge_classes():
    all_badges_response = requests.post(
       open_badge.config.get('TRIPLESTORE_URL'),
       data={"query": FIND_ALL_CLASSES,
             "format": "json"})
    if all_badges_response.status_code > 399:
        abort(502)
    bindings = all_badges_response.json().get('results').get('bindings')
    return [(r.get('altName')['value'], r.get('name')['value']) for r in bindings]
      

@open_badge.route("/Assertion/", methods=["POST", "GET"])
def add_badge_assertion():
    assertion_form = NewAssertion()
    assertion_form.badge.choices = get_badge_classes()
    if request.method.startswith("POST"):
        if form.validate_on_submit():
             redirect("/Assertion/{}".format(uuid))
    return render_template(
        "assertion.html",
         form=assertion_form)

@open_badge.route("/Assertion/<event>/<uuid>")
@open_badge.route("/Assertion/<event>/<uuid>.json")
@produces('application/json')
def badge_assertion(event=None):
    """Route returns individual badge assertion json or 404 error if not
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


@open_badge.route("/BadgeClass/", methods=["POST", "GET"])
def add_badge_class():
    """Displays Form for adding a BadgeClass Form"""
    badge_class_form = NewBadgeClass()
    if request.method.startswith("POST"):
        badge_url, badge_slug = new_badge_class(
            name=badge_class_form.name.data,
            description=badge_class_form.description.data,
            image=badge_class_form.image_file.data,
            startDate=badge_class_form.startDate.data,
            endDate=badge_class_form.endDate.data,
            tags=badge_class_form.tags.data,
            issuer=open_badge.config.get("ORGANIZATION"),
            criteria=badge_class_form.criteria.data)
        redirect(url_for('open_badge.badge_class', badge_classname=badge_slug))
    return render_template(
        "badge_class.html",
        form=badge_class_form)

    

@open_badge.route("/BadgeClass/<badge_classname>")
@open_badge.route("/BadgeClass/<badge_classname>.json")
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

@open_badge.route("/Criteria/<badge>")
@produces('application/json')
def badge_criteria(badge):
    """Route displays the criteria for the badge class

    Args:
        badge: Name of Badge (Camp, Projects, Institutions, etc.)

    Returns:
        JSON of badge's critera
    """
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


@open_badge.route("/Issuer")
def badge_issuer_organization():
    "Route generates JSON for the badge issuer's organization"
    organization = {
        "name": badge_app.config['BADGE_ISSUER_NAME'],
        "url": badge_app.config['BADGE_ISSUER_URL']
    }
    return jsonify(organization)


@open_badge.route("/<badge>.png")
@open_badge.route("/<badge>/<uid>.png")
def badge_image(badge, uid=None):
    if uid is not None:
        img_url = repository.sparql(uuid_template(uuid=uid))
    else:
        if not badge in badges:
            abort(404)
        img_url = '/'.join(str(badges[badge]['url']).split("/")[:-1])
    img_response = requests.get(img_url)
    if img_response.status_code > 399:
        abort(500)
    return Response(img_response.text, mimetype='image/png')
