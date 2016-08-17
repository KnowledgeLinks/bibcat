"""Flask Blueprint for bibcat unique views"""
__author__ = "Jeremy Nelson, Mike Stabile"

import time
import base64
import re
import io
import json
import requests
import copy
from urllib.request import urlopen
from werkzeug import wsgi
from flask import Flask, abort, Blueprint, jsonify, render_template, Response,\
        request, redirect, url_for, send_file, current_app
from flask.ext.login import login_required, login_user, current_user, \
        logout_user
from flask_wtf import CsrfProtect
from rdfframework import RdfProperty, get_framework as rdfw
from rdfframework.utilities import render_without_request, code_timer, \
        remove_null, pp, clean_iri, uid_to_repo_uri, cbool, make_list, iri, \
        fw_config, convert_spo_to_dict, convert_obj_to_rdf_namespace
from rdfframework.forms import rdf_framework_form_factory 
from rdfframework.api import rdf_framework_api_factory, Api
from rdfframework.security import User
from rdfframework.sparql import run_sparql_query

bibcat = Blueprint("bibcat", __name__,
                       template_folder="templates")
bibcat.config = {}

@bibcat.record
def record_params(setup_state):
    """Function takes the setup_state and updates configuration from
    the active application.

    Args:
        setup_state -- Setup state of the application.
    """
    app = setup_state.app
    bibcat.config = dict(
        [(key, value) for (key, value) in app.config.items()]
    )
    
DEBUG = True

@bibcat.route("/institutions/index.html")
@bibcat.route("/institutions")
@bibcat.route("/institutions/")
def institution_list_path():
    """ Displays a list of insitutions with a link to their catalog """
    demo_orgs = [{"link":{'value':"#"},"name":{'value':"org1"}},
                 {"link":{'value':"#"},"name":{'value':"org2"}},
                 {"link":{'value':"#"},"name":{'value':"org3"}}] 
    orgs = run_sparql_query(ORGS_SPARQL) 
    template = render_template("/institutions.html",
                               orgs=orgs)
    return template

@bibcat.route("/helditems")
def institution_helditem_path():
    """ Displays a list of insitutions with a link to their catalog """
    institution = request.args.get("institution")
    if institution is None:
        return redirect(url_for("bibcat.institution_list_path"))
    helditems = run_sparql_query(ORG_ITEMS_SPARQL.format(iri(institution)))   
    template = render_template("/helditems.html",
                               helditems=helditems,
                               org=clean_iri(institution))
    return template 

@bibcat.route("/instances")
def instances_path():
    """ Displays a list of insitutions with a link to their catalog """
    instances = run_sparql_query(INSTANCES_SPARQL)   
    template = render_template("/instances.html",
                               instances=instances)
    return template 
 
@bibcat.route("/item")
def instance_path():
    """ Displays the turtle grpah of an instance """
    item_id = clean_iri(request.args.get("id"))
    if item_id is None:
        return redirect(url_for("bibcat.institution_list_path"))
    item_data = run_sparql_query(INSTANCE_SPARQL.format(iri(item_id)))
    cdata = convert_spo_to_dict(item_data)
    nsdata = convert_obj_to_rdf_namespace(cdata)
    rtn_data = copy.deepcopy(nsdata)
    title = {}
    item_type = None
    for key, value in nsdata.items():
        item_data = False
        if key == item_id:
            item_data = True
        for subkey, val2 in value.items():
            if subkey == "bf_title" and item_data:
                title_key = val2
                if isinstance(val2, list):
                    title_key = val2[0]
                title = dict.copy(nsdata[title_key])
            elif subkey == "rdf_type" and item_data:
                item_type = val2.replace("bf_", "")
            if re.match(r'^t\d', str(val2)):
                rtn_data[key][subkey] = dict.copy(nsdata[val2])
            elif isinstance(val2, list):
                list_objs = []
                for item in val2:
                    if re.match(r'^t\d', str(item)):
                        list_objs.append(dict.copy(nsdata[item]))
                    else:
                        list_objs.append(item)
                rtn_data[key][subkey] = list_objs
    for key, value in nsdata.items():
        if re.match(r'^t\d', key):
            del rtn_data[key]
    template = render_template("/item.html",
                               item=rtn_data,
                               title=title,
                               item_type=item_type)
    return template 

ORGS_SPARQL = """  
SELECT ?name ?id {
  ?id a schema:Organization .
  ?id schema:name ?name
  bind(concat("/helditems?institution=",str(?id),"") as ?link)
}
ORDER BY ?name"""

ORG_ITEMS_SPARQL = """
SELECT ?i ?title ?aut (group_concat(?isbn1; SEPARATOR=", ") as ?isbn)
{{
  SELECT DISTINCT ?i ?title ?aut ?isbn1
  {{
    ?s bf:heldBy {}.
    ?s bf:itemOf ?i .
    ?i bf:title ?bn_t .
    ?bn_t bf:mainTitle ?title .

    optional {{
          ?i relators:aut ?bn_aut .
          ?bn_aut schema:alternativeName ?aut
       }} .
    optional {{
      ?i bf:identifiedBy ?bn_id .
      ?bn_id a bf:Isbn .
      ?bn_id rdf:value ?isbn1 }} .
  }}
  ORDER BY ?title ?isbn

}}
GROUP BY ?i ?title ?aut"""

WORKS_SPARQL = """
SELECT ?i ?title ?aut (group_concat(?isbn1; SEPARATOR=", ") as ?isbn)
{{
  SELECT DISTINCT ?i ?title ?aut ?isbn1
  {{
    ?i bf:title ?bn_t .
    ?bn_t bf:mainTitle ?title .

    optional {{
          ?i relators:aut ?bn_aut .
          ?bn_aut schema:alternativeName ?aut
       }} .
    optional {{
      ?i bf:identifiedBy ?bn_id .
      ?bn_id a bf:Isbn .
      ?bn_id rdf:value ?isbn1 }} .
  }}
  ORDER BY ?title ?isbn

}}
GROUP BY ?i ?title ?aut"""

INSTANCES_SPARQL = """
SELECT ?s ?title ?aut (group_concat(?isbn1; SEPARATOR=", ") as ?identifiers)
{{
  SELECT DISTINCT ?s ?title ?aut ?isbn1
  {{
    ?s a bf:Instance .
    ?s bf:title ?bn_t .
    ?bn_t bf:mainTitle ?title .

    optional {{
          ?s relators:aut ?bn_aut .
          ?bn_aut schema:alternativeName ?aut
       }} .
    optional {{
      ?s bf:identifiedBy ?bn_id .
      #?bn_id a bf:Isbn .
      ?bn_id rdf:value ?isbn1 }} .
  }}
  #ORDER BY ?title ?isbn

}}
GROUP BY ?s ?title ?aut
limit 25
"""
INSTANCE_SPARQL = """
SELECT
  ?s ?p ?o
WHERE
{{
  {{
  	BIND({0} as ?s) .
  	?s ?p ?o
  }} union {{
    BIND({0} as ?s1) .
    ?s1 ?p1 ?s .
    ?s ?p ?o
    filter(isBlank(?s)||isiri(?s))
    filter(?p1!=rdf:type)
  }} union {{
    BIND({0} as ?s1) .
    ?s1 ?p1 ?s2 .
    ?s2 ?p2 ?s .
    ?s ?p ?o .
    filter(isiri(?s2))
    filter(isblank(?s))
  }}
}}"""
INSTANCE_SPARQL_new = """
SELECT DISTINCT
  ?s ?p ?o
WHERE
{{
  {{
    BIND({0} as ?s) .
    ?s ?p ?o
  }} union {{
    BIND({0} as ?s1) .
    ?s1 ?p1 ?s .
    ?s ?p ?o
    filter(isBlank(?s)||isiri(?s))
    filter(?p1!=rdf:type)
  }} union {{
    BIND({0} as ?s1) .
    ?s1 ?p1 ?s2 .
    ?s2 ?p2 ?s .
    ?s ?p ?o .
    filter(isiri(?s2))
    filter(isblank(?s))
  }} union {{
    BIND({0} as ?o) .
    ?s ?p ?o .
  }} union {{
    BIND({0} as ?o1) .
    ?s ?p1 ?o1 .
    ?s ?p ?o
    filter(isBlank(?s)||isiri(?s))
    filter(?p1!=rdf:type)
  }} union {{
    BIND({0} as ?o1) .
    ?s2 ?p1 ?o1 .
    ?s2 ?p2 ?s .
    ?s ?p ?o .
    filter(isiri(?s2))
    filter(isblank(?s))
  }}
}}
"""