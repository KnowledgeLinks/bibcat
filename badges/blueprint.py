"""Flask Blueprint for Open Badges"""
__author__ = "Jeremy Nelson, Mike Stabile"

import json
import requests
import time
from flask import abort, Blueprint, jsonify, render_template, Response, request
from flask import redirect, url_for
from flask_negotiate import produces
from flask.ext.login import login_required, login_user

from . import new_badge_class, issue_badge
from .forms import NewBadgeClass, NewAssertion, rdf_form_factory
from .graph import FIND_ALL_CLASSES, FIND_IMAGE_SPARQL
from .utilities import render_without_request
from .rdfframework import rdf_framework_form_factory, load_form_select_options
from .rdfframework import get_framework, calculate_time_log, code_timer
from .user import User

open_badge = Blueprint("open_badge", __name__,
                       template_folder="templates")
open_badge.config = {}

@open_badge.record
def record_params(setup_state):
    """Function takes the setup_state and updates configuration from
    the active application.

    Args:
        setup_state -- Setup state of the application.
    """
    app = setup_state.app
    open_badge.config = dict(
        [(key, value) for (key, value) in app.config.items()]
    )
    base_url = open_badge.config.get('ORGANIZATION').get('url')
    triplestore_url = open_badge.config.get('TRIPLESTORE_URL')
    # Strip off trailing forward slash for TTL template
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    # if the extensions exist in the triplestore drop the graph
    stmt = "DROP GRAPH <http://knowledgelinks.io/ns/application-framework/>;"
    drop_extensions = requests.post(
        url=triplestore_url,
        params={"update": stmt})
    # render the extensions with the base URL
    # must use a ***NON FLASK*** routing since flask is not completely
    # initiated
    rdf_resource_templates = [
        "kds-app.ttl",
        "kds-vocab.ttl",
        "kds-resources.ttl"]
    rdf_data = []
    for template in rdf_resource_templates:
        rdf_data.append(
            render_without_request(
                template,
                base_url=base_url))
    # load the extensions in the triplestore
    context_uri = "http://knowledgelinks.io/ns/application-framework/"
    for data in rdf_data:
        result = requests.post(
            url=triplestore_url,
            headers={"Content-Type": "text/turtle"},
            params={"context-uri": context_uri},
            data=data)
        if result.status_code > 399:
            raise ValueError("Cannot load extensions in {}".format(
                triplestore_url))
    #get_framework()

def get_badge_classes():
    """Helper function retrieves all badge classes from the triplestore"""
    all_badges_response = requests.post(
        open_badge.config.get('TRIPLESTORE_URL'),
        data={"query": FIND_ALL_CLASSES,
              "format": "json"})
    if all_badges_response.status_code > 399:
        abort(502)
    bindings = all_badges_response.json().get('results').get('bindings')
    #uid = re.sub(r'^(.*[#/])','',bindings[0].get('subject')['value'])
    #, re.sub(r'^(.*[#/])','',r.get('subject')['value'])
    return [(r.get('altName')['value'],
             r.get('name')['value']) for r in bindings]
@open_badge.route("/")
def base_path():
    return ""

@open_badge.route("/login", methods=["GET", "POST"])
def login_user_view():
    """Login view for badges"""
    val = None
    login_form = rdf_framework_form_factory(
        "LoginForm")
    if request.method.startswith("POST"):
        form = login_form(request.form)
        val = form.validate()
        username = request.form.get("username")
        pwd = request.form.get("password")
        user = User(username=username, password=pwd)
        login_user(user, remember=True)
        redirect("/")
    else:
        form = login_form()
    return render_template(
        "app_form_template.html",
        actionURL=url_for("open_badge.login_user_view"),
        form=form,
        jsonFields=json.dumps(
            form.rdfFieldList,
            indent=4),
        validated=val)

@open_badge.route("/test/", methods=["POST", "GET"])
def test_rdf_class():
    """View for displaying a test RDF class"""
    x=y #This is an intentional error to cause a break in the code
    return "<pre>{}</pre>".format(json.dumps({"message": "test rdf class"}))

RDF_CLASS_JSON = '''<table>
  <tr>
    <td><h1>Application JSON</h1></td>
    <td><h1>Class JSON</h1></td>
	<td><h1>Form Json</h1></td>
  </tr>
  <tr>
    <td style='vertical-align:top'><pre>{0}<</pre></td>
    <td style='vertical-align:top'><pre>{1}</pre></td>
	<td style='vertical-align:top'><pre>{2}<</pre></td>
  </tr>
</table>'''

@open_badge.route("/rdfjson/", methods=["POST", "GET"])
def form_rdf_class():
    """View displays the RDF json"""
    form_dict = get_framework().rdf_form_dict
    class_dict = get_framework().rdf_class_dict
    app_dict = get_framework().rdf_app_dict
    return RDF_CLASS_JSON.format(
        json.dumps(app_dict, indent=2), 
        json.dumps(class_dict, indent=2),
        json.dumps(form_dict, indent=2))

@open_badge.route("/<form_name>/<form_instance>",
    methods=["POST", "GET"])
@open_badge.route("/<form_name>/<form_instance>.html",
    methods=["POST", "GET"])
def rdf_class_forms(form_name,form_instance):
    """View for displaying forms

    Args:
        form_instance -- Type of form (new, edit)
        
    params:
        id -- the subject uri of the form data to lookup 
    """
    _display_mode = False
    code_timer().log("formTest",
                    "form render start for: {}/{}".format(\
                    form_name,form_instance))
    if not get_framework().formExists(form_name,form_instance):
        return render_template(
            "error_page_template.html",
            error_message="The web address is invalid")
    code_timer().log("formTest","End test form path")
    # generate the form class
    code_timer().log("formTest","initial form creation start")   
    form_class = rdf_framework_form_factory(
        form_name,
        'http://knowledgelinks.io/ns/data-resources/'+form_instance)
    code_timer().log("formTest","initial form creation end")
    # if request method is post
    if request.method == "POST":
        # let form load with post data
        form = form_class()
        # select field options have to be loaded before form is validated
        form = load_form_select_options(form)
        # validate the form 
        if form.validate():
            # if validated save the form 
            if request.args.get("id") and form_instance == "EditForm":
                form.dataSubjectUri = request.args.get("id") 
            formSaveResults = get_framework().saveForm(form)
            if formSaveResults.get("success"):
                return "<pre>{}</pre>".format(json.dumps(\
                        formSaveResults, indent=4)) 
            else:
                #print("################## Invalid Form")
                form = formSaveResults.get("form")
    # if not POST, check the args and form instance
    else:
        # if params are present for any forms not in the below form remove 
        # the params
        code_timer().log("formTest","start non post testing")
        if form_instance not in ["EditForm","DisplayForm","Login"] and \
                request.args.get("id"):
            redirect_url = url_for("open_badge.rdf_class_forms",
                                    form_name=form_name,
                                    form_instance=form_instance)
            return redirect(redirect_url)
        # if the there is no ID argument and on the editform instance -> 
        # redirect to NewForm
        if form_instance in ["EditForm","DisplayForm"] and \
                not request.args.get("id"):
            redirect_url = url_for("open_badge.rdf_class_forms",
                                    form_name=form_name,
                                    form_instance="NewForm")
            return redirect(redirect_url)
        # if the display form does not have an ID return an error
        if form_instance in ["DisplayForm"] and not request.args.get("id"):
            return render_template(
                    "error_page_template.html",
                    error_message="The item does not exist") 
        # if the there is an ID argument and on the editform instance -> 
        # query for the save item
        code_timer().log("formTest","end non post testing")
        if request.args.get("id") and form_instance \
                in ["EditForm","DisplayForm"]:
            if form_instance == "DisplayForm":
                _display_mode = True
            code_timer().log("formTest","load form data create form class")
            form = form_class()
            code_timer().log("formTest",\
                    "load form data end create class start data load")
            formData = get_framework().getFormData(
                form,
                subjectUri=request.args.get("id"))
            code_timer().log("formTest",\
                    "load form data data query completed")
            print("^^^^^^^^^^^^^^^^ formData: ",formData)
            if len(formData.get('queryData',{})) > 0:
                form = form_class(formData.get("formdata"))
                code_timer().log("formTest",\
                        "form loaded with data")
            else:
                return render_template(
                    "error_page_template.html",
                    error_message="The item does not exist")  
                      
        # if not on EditForm or DisplayForm render form
        else:
            form = form_class()
        code_timer().log("formTest","start query options load")
        form = load_form_select_options(\
                form,
                url_for("open_badge.base_path"))
        code_timer().log("formTest","end query options load")
    template = render_template(
        "app_form_template.html",
        actionUrl=request.url,
        form=form,
        display_mode = _display_mode,
        dateFormat = get_framework().rdf_app_dict['application'].get(\
                'dataFormats',{}).get('javascriptDateFormat',''),
        jsonFields=json.dumps(form.rdfFieldList, indent=4),
        debug=request.args.get("debug",False))
    code_timer().log("formTest","template rendered")
    code_timer().printTimer("formTest")
    code_timer().deleteTimer("formTest")
    return template
