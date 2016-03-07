"""Flask Blueprint for Open Badges"""
__author__ = "Jeremy Nelson, Mike Stabile"

import time
import urllib
import base64
import re
import io
import json
import requests
import falcon
from flask import abort, Blueprint, jsonify, render_template, Response, request
from flask import redirect, url_for, send_file
from flask_negotiate import produces
from flask.ext.login import login_required, login_user

from . import new_badge_class, issue_badge
from rdfframework.utilities import render_without_request, code_timer, \
        remove_null, pp, clean_iri, uid_to_repo_uri
from rdfframework import get_framework as rdfw
from rdfframework.forms import rdf_framework_form_factory 
from rdfframework.api import rdf_framework_api_factory
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
    # initialize the rdfframework
    rdfw(config=open_badge.config)


@open_badge.route("/")
def base_path():
    return ""

@open_badge.route("/image/<image_id>", methods=["GET"])
def image_path(image_id):
    ''' view passes the specified fedora image based on the uuid'''
    _repo_image_uri = uid_to_repo_uri(image_id)
    repo_image_link = urllib.request.urlopen(_repo_image_uri)
    image = repo_image_link.read()  
    return send_file(io.BytesIO(image),
                     attachment_filename='img.png',
                     mimetype='image/png')

@open_badge.route("/fedora_image", methods=["GET"])
def fedora_image_path():
    ''' view for finding an image based on the fedora uri'''
    if request.args.get("id"):
        uid = re.sub(r'^(.*[#/])','',request.args.get("id"))
        return redirect(url_for("open_badge.image_path",
                         image_id=uid))    
      
'''@open_badge.route("/login", methods=["GET", "POST"])
def login_user_view():
    """Login view for badges"""
    val = None
    login_form = rdf_framework_form_factory(
        "login/")
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
        validated=val)'''

@open_badge.route("/test/", methods=["POST", "GET"])
def test_rdf_class():
    """View for displaying a test RDF class"""
    f=rdfw() #This is an intentional error to cause a break in the code
    y=z
    return "<pre>{}</pre>".format(json.dumps({"message": "test rdf class"}))


@open_badge.route("/rdfjson/", methods=["POST", "GET"])
def form_rdf_class():
    """View displays the RDF json"""
    form_dict = rdfw().rdf_form_dict
    class_dict = rdfw().rdf_class_dict
    app_dict = rdfw().rdf_app_dict
    api_dict = rdfw().rdf_api_dict
    table_template = '''
    <style>
        table.fixed {{ 
            table-layout:fixed;
            width: 2000px
        }}
        table.fixed td {{ 
            overflow: hidden;
            vertical-align:top; 
        }}
    </style>
    <table class="fixed">
        <col width="20%" />
        <col width="20%" />
        <col width="20%" />
        <col width="20%" />
        <col width="20%" />
        <col width="20%" />
        <tr>
            <td><h1>Application JSON</h1></td>
            <td><h1>Class JSON</h1></td>
            <td><h1>Form Paths</h1></td>
        	<td><h1>Form Json</h1></td>
        	<td><h1>API List</h1></td>
        	<td><h1>API Json</h1></td>     	
        </tr>
        <tr>
            <td><pre>{0}</pre></td>
            <td><pre>{2}</pre></td>
            <td><pre>{1}</pre></td>
        	<td><pre>{3}</pre></td>
        	<td><pre>{5}</pre></td>
        	<td><pre>{4}</pre></td>
        </tr>
    </table>'''
    return table_template.format(
        json.dumps(app_dict, indent=2),
        json.dumps(rdfw().form_list, indent=2), 
        json.dumps(class_dict, indent=2),
        json.dumps(form_dict, indent=2),
        json.dumps(api_dict, indent=2),
        json.dumps(rdfw().api_list, indent=2))

@open_badge.route("/api/<api_name>/<id_value>.<ext>", methods=["POST", "GET"])
@open_badge.route("/api/<api_name>", methods=["POST", "GET"])
def rdf_api(api_name, id_value=None, ext=None):
    """View for displaying forms

    Args:
        api_name -- url path of the api (new, edit)
        ext -- url extension for the api ie (.json, .html)
        
    params:
        id -- the item to lookup 
    """
    api_repsonder = falcon.API()
    _api_path = "|".join(remove_null([api_name, ext]))
    _api_exists = rdfw().api_exists(_api_path)
    if _api_exists is False:
        return render_template(
            "error_page_template.html",
            error_message="The web address is invalid")
    api_uri = _api_exists.get("api_uri")
    # generate the api class
    base_url = "%s%s" % (request.url_root[:-1], url_for("open_badge.base_path")) 
    current_url = request.url
    base_api_url = "%s%sapi/" % (request.url_root[:-1],
                                   url_for("open_badge.base_path"))
    api_url = request.base_url
    api_class = rdf_framework_api_factory(_api_path, 
                                          base_url=base_url, 
                                          current_url=current_url,
                                          base_api_url=base_api_url,
                                          api_url=api_url) 
     
    # if request method is post 
    if request.method == "POST":
        # let api load with post data
        api = api_class(id_value=id_value)
        # validate the form 
        if api.validate():
            # if validated save the form 
            api.save()
            if api.save_state == "success":
                return api.return_message
    # if not POST, check the args and api instance/extension
    else:
        api = api_class()
        api_data = rdfw().get_obj_data(api, id_value=id_value)
        #pp.pprint(api_data['form_data'])
        if not (len(api_data['query_data']) > 0):
            return render_template(
                "error_page_template.html",
                error_message="The item does not exist") 
        else:
            return_type = api.rdf_instructions.get("kds_returnType")
            if return_type == "file":
                repo_uri = clean_iri(list(api_data['obj_json'].values())[0])
                repo_link = urllib.request.urlopen(repo_uri)
                repo_file = repo_link.read()  
                return send_file(io.BytesIO(repo_file),
                     attachment_filename="%s.%s" % (id_value, ext),
                     mimetype=api.rdf_instructions.get("kds_mimeType"))
            else:
                return "<pre>{}</pre>".format(json.dumps(api_data['obj_json'],indent=4)) 

        
@open_badge.route("/<form_name>.html", methods=["POST", "GET"])
@open_badge.route("/<form_name>", methods=["POST", "GET"])
@open_badge.route("/<form_name>/<form_instance>", methods=["POST", "GET"])
@open_badge.route("/<form_name>/<form_instance>.html", methods=["POST", "GET"])
def rdf_class_forms(form_name, form_instance=None):
    """View for displaying forms

    Args:
        form_instance -- Type of form (new, edit)
        
    params:
        id -- the subject uri of the form data to lookup 
    """
    _display_mode = False
    _form_path = "/".join(remove_null([form_name, form_instance]))
    _form_exists = rdfw().form_exists(_form_path)
    if _form_exists is False:
        return render_template(
            "error_page_template.html",
            error_message="The web address is invalid")
    instance_uri = _form_exists.get("instance_uri")
    form_uri = _form_exists.get("form_uri")
    # generate the form class
    form_class = rdf_framework_form_factory(_form_path, \
            base_url=url_for("open_badge.base_path"), 
            current_url=request.url)
            
    # if request method is post 
    if request.method == "POST":
        # let form load with post data
        form = form_class(subject_uri=request.args.get("id"))
        # validate the form 
        if form.validate():
            # if validated save the form 
            form.save()
            if form.save_state == "success":
                return redirect(form.redirect_url(params=request.args))

        #form = form_class(subject_uri=request.args.get("id"))
    # if not POST, check the args and form instance
    else:
        # if params are present for any forms that are not in any of 
        # the below forms remove the params
        if instance_uri not in ["kdr_EditForm", "kdr_DisplayForm", "kdr_Login"]\
                 and request.args.get("id"):
            redirect_url = url_for("open_badge.rdf_class_forms",
                                    form_name=form_name,
                                    form_instance=form_instance)
            return redirect(redirect_url)
        # if the there is no ID argument and on the editform instance -> 
        # redirect to NewForm
        if instance_uri in ["kdr_EditForm","kdr_DisplayForm"] and \
                not request.args.get("id"):
            redirect_url = url_for("open_badge.base_path") + \
                    rdfw().get_form_path(form_uri, "kdr_NewForm")
            return redirect(redirect_url)
        # if the display form does not have an ID return an error
        if instance_uri in ["kdr_DisplayForm"] and not request.args.get("id"):
            return render_template(
                    "error_page_template.html",
                    error_message="The item does not exist") 
        # if the there is an ID argument and on the editform instance -> 
        # query for the save item
        if request.args.get("id") and instance_uri \
                in ["kdr_EditForm","kdr_DisplayForm"]:
            if instance_uri == "kdr_DisplayForm":
                _display_mode = True
            form_data = rdfw().get_obj_data(form_class(\
                    no_query=True, subject_uri=request.args.get("id")))
            #pp.pprint(form_data['form_data'])
            form = form_class(form_data['obj_data'],\
                      query_data=form_data['query_data'],\
                      subject_uri=request.args.get("id"))
            if not (len(form_data['query_data']) > 0):
                return render_template(
                    "error_page_template.html",
                    error_message="The item does not exist")  
                      
        # if not on EditForm or DisplayForm render form
        else:
            form = form_class()
    
    template = render_template(
        "/forms/default/app_form_template.html",
        actionUrl=request.url,
        form=form,
        display_mode = _display_mode,
        dateFormat = rdfw().app.get(\
                'kds_dataFormats',{}).get('kds_javascriptDateFormat',''),
        debug=request.args.get("debug",False))
    return template
    
