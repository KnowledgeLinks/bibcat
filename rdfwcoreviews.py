"""Flask Blueprint for rdfw core views"""
__author__ = "Jeremy Nelson, Mike Stabile"

import time
import base64
import re
import io
import json
import requests
from urllib.request import urlopen
from werkzeug import wsgi
from flask import Flask, abort, Blueprint, jsonify, render_template, Response, request
from flask import redirect, url_for, send_file, current_app
from flask.ext.login import login_required, login_user, current_user
from flask_wtf import CsrfProtect
from rdfframework import RdfProperty, get_framework as rdfw
from rdfframework.utilities import render_without_request, code_timer, \
        remove_null, pp, clean_iri, uid_to_repo_uri, cbool, make_list
from rdfframework.forms import rdf_framework_form_factory 
from rdfframework.api import rdf_framework_api_factory, Api
from rdfframework.security import User

rdfw_core = Blueprint("rdfw_core", __name__,
                       template_folder="templates")
rdfw_core.config = {}

@rdfw_core.record
def record_params(setup_state):
    """Function takes the setup_state and updates configuration from
    the active application.

    Args:
        setup_state -- Setup state of the application.
    """
    app = setup_state.app
    rdfw_core.config = dict(
        [(key, value) for (key, value) in app.config.items()]
    )
    
DEBUG = True

@rdfw_core.route("/")
def base_path():
    return "<h1>base<h1>"

    
@rdfw_core.route("/image/<image_id>", methods=["GET"])
def image_path(image_id):
    ''' view passes the specified fedora image based on the uuid'''
    if not DEBUG:
        debug = False
    else:
        debug = False
    if debug: print("START image_path - blueprint.py ----------------------\n")
    if debug: print("\timage_id: ", image_id)
    _repo_image_uri = uid_to_repo_uri(image_id)
    if debug: print("\t_repo_image_uri: ", _repo_image_uri)
    repo_image_link = urlopen(_repo_image_uri)
    # The File wrapper is causing issues in the live environment
    # need to delete before sending byte stream
    if debug: print("\t wsgi.file_wrapper pre: ",\
            request.environ.get('wsgi.file_wrapper'))
    if request.environ.get('wsgi.file_wrapper') is not None:
        del(request.environ['wsgi.file_wrapper'])
    if debug: print("\t wsgi.file_wrapper post: ",\
            request.environ.get('wsgi.file_wrapper'))
    image = repo_image_link.read() 
    if debug: print("\tlen(image): ", len(image))
    if debug: print("END image_path - blueprint.py ------------------------\n")
    return send_file(io.BytesIO(image),
                     attachment_filename='%s.png' % image_id,
                     mimetype='image/png')

@rdfw_core.route("/fedora_image", methods=["GET"])
def fedora_image_path():
    ''' view for finding an image based on the fedora uri'''
    if request.args.get("id"):
        uid = re.sub(r'^(.*[#/])','',request.args.get("id"))
        return redirect(url_for("app.image_path",
                         image_id=uid))    
      
@rdfw_core.route("/test/", methods=["POST", "GET"])
def test_rdf_class():
    """View for displaying a test RDF class"""
    f=rdfw() #This is an intentional error to cause a break in the code
    y=z
    return "<pre>{}</pre>".format(json.dumps({"message": "test rdf class"}))

@rdfw_core.route("/api/<api_name>/<id_value>.<ext>", methods=["POST", "GET"])
@rdfw_core.route("/api/<api_name>", methods=["POST", "GET"])
def rdf_api(api_name, id_value=None, ext=None):
    """View for displaying forms

    Args:
        api_name -- url path of the api (new, edit)
        ext -- url extension for the api ie (.json, .html)
        
    params:
        id -- the item to lookup 
    """
    if not DEBUG:
        debug = False
    else:
        debug = False
    if debug: print("START rdf_api blueprint.py ---------------------------\n")
    api_repsonder = falcon.API()
    _api_path = "|".join(remove_null([api_name, ext]))
    _api_exists = rdfw().api_exists(_api_path)
    if _api_exists is False:
        return render_template(
            "error_page_template.html",
            error_message="The web address is invalid")
    api_uri = _api_exists.get("api_uri")
    # generate the api class
    base_url = "%s%s" % (request.url_root[:-1], url_for("app.base_path")) 
    current_url = request.url
    base_api_url = "%s%sapi/" % (request.url_root[:-1],
                                   url_for("app.base_path"))
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
                if debug: print("END rdf_api blueprint.py ---POST--------\n")
                return api.return_message
    # if not POST, check the args and api instance/extension
    else:
        api = api_class()
        api_data = rdfw().get_obj_data(api, id_value=id_value)
        #pp.pprint(api_data['form_data'])
        if not (len(api_data['query_data']) > 0):
            '''return render_template(
                "error_page_template.html",
                error_message="The item does not exist") '''
            return abort(400)
        else:
            return_type = api.rdf_instructions.get("kds_returnType")
            if return_type == "file":
                repo_uri = clean_iri(list(api_data['obj_json'].values())[0])
                repo_link = urlopen(repo_uri)
                repo_file = repo_link.read() 
                # The File wrapper is causing issues in the live environment
                # need to delete before sending byte stream
                if debug: print("\t wsgi.file_wrapper pre: ",\
                        request.environ.get('wsgi.file_wrapper'))
                if request.environ.get('wsgi.file_wrapper') is not None:
                    del(request.environ['wsgi.file_wrapper'])
                if debug: print("\t wsgi.file_wrapper post: ",\
                        request.environ.get('wsgi.file_wrapper')) 
                if debug: print("END rdf_api blueprint.py --- file send ---\n")
                return send_file(io.BytesIO(repo_file),
                #return send_file(repo_link,
                     attachment_filename="%s.%s" % (id_value, ext),
                     mimetype=api.rdf_instructions.get("kds_mimeType"))
            else:
                #return "<pre>{}</pre>".format(json.dumps(api_data['obj_json'],indent=4)) 
                if debug: print("END rdf_api blueprint.py --- json --------\n")
                return jsonify(api_data['obj_json'])
        
@rdfw_core.route("/<form_name>.html", methods=["POST", "GET"])
@rdfw_core.route("/<form_name>", methods=["POST", "GET"])
@rdfw_core.route("/<form_name>/<form_instance>", methods=["POST", "GET"])
@rdfw_core.route("/<form_name>/<form_instance>.html", methods=["POST", "GET"])
def rdf_class_forms(form_name, form_instance=None):
    """View for displaying forms

    Args:
        form_instance -- Type of form (new, edit)
        
    params:
        id -- the subject uri of the form data to lookup 
    """
    _display_mode = False
    _form_path = "/".join(remove_null([form_name, form_instance]))
    # test to see if the form exists
    _form_exists = rdfw().form_exists(_form_path)
    if _form_exists is False:
        return render_template(
            "error_page_template.html",
            error_message="The web address is invalid")
    # if the form exists continue
    instance_uri = _form_exists.get("instance_uri")
    form_uri = _form_exists.get("form_uri")
    # generate the form class
    form_class = rdf_framework_form_factory(_form_path, \
            base_url=url_for("rdfw_core.base_path"), 
            current_url=request.url)
    # test to see if the form requires a login
    login_message = None
    if cbool(form_class.rdf_instructions.get("kds_loginRequired",False)) is \
            True:
        if isinstance(current_user.is_authenticated, bool):
            auth = current_user.is_authenticated
        else:
            auth = current_user.is_authenticated()
        if not auth:
            current_app.login_manager.login_message = \
                    "Please log in to access this page"
            return current_app.login_manager.unauthorized()        
    # if request method is post 
    if request.method == "POST":
        # let form load with post data
        form = form_class(subject_uri=request.args.get("id"))
        # validate the form 
        if form.validate():
            # if validated save the form 
            obj = form.save()
            if form.save_state == "success":
                if isinstance(form.save_results, User):
                    login_user(form.save_results)
                    #x=y
                return redirect(form.redirect_url(params=request.args))

        #form = form_class(subject_uri=request.args.get("id"))
    # if not POST, check the args and form instance
    else:
        # if params are present for any forms that are not in any of 
        # the below forms remove the params
        if instance_uri not in ["kdr_EditForm", "kdr_DisplayForm", "kdr_Login"]\
                 and request.args.get("id"):
            redirect_url = url_for("app.rdf_class_forms",
                                    form_name=form_name,
                                    form_instance=form_instance)
            return redirect(redirect_url)
        # if the there is no ID argument and on the editform instance -> 
        # redirect to NewForm
        if instance_uri in ["kdr_EditForm","kdr_DisplayForm"] and \
                not request.args.get("id"):
            redirect_url = url_for("app.base_path") + \
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
        debug=request.args.get("debug",False),
        login_message=login_message)
    return template
    

@rdfw_core.route("/api/form_generic_prop/<class_uri>/<prop_uri>",
                  methods=["POST", "GET"])
def rdf_generic_api(class_uri, prop_uri):
    if not DEBUG:
        debug = False
    else:
        debug = True
    if debug: print("START rdf_generic_api ----------------------------\n")
    subject_uri = request.args.get("id")
    data = request.form.get("dataValue")
    subject_uri = request.form.get("id",subject_uri)
    if debug: print("class_uri: %s  prop_uri: %s" % (class_uri, prop_uri))
    if debug: print('subject_uri: ', subject_uri)
    if debug: print('data: ', data)
    if prop_uri in ["obi_claimDate","kds_errorLog"] and class_uri == "obi_Assertion":
        if hasattr(request, "form"):
            csrf = request.form.get("csrf")
    else:
        if debug: print("aborting **************")
        return abort(400)  
    subject_uri = request.args.get("id") 
    data = request.form.get("dataValue")
    subject_uri = request.form.get("id",subject_uri)
    #if debug: print("REQUEST dict: \n", pp.pformat(request.__dict__))
    rdf_class = getattr(rdfw(), class_uri)
    prop_json = rdf_class.kds_properties.get(prop_uri)
    prop_json['kds_classUri'] = class_uri
    prop_json['kds_apiFieldName'] = prop_uri
    prop = RdfProperty(prop_json, data, subject_uri)
    base_url = "%s%s" % (request.url_root[:-1], url_for("app.base_path")) 
    current_url = request.url
    base_api_url = "%s%sapi/form_generic_prop/" % (request.url_root[:-1],
                                   url_for("app.base_path"))
    if debug:
        print('rdf_class: ', rdf_class)
        print('prop_json: ', prop_json)
        print('prop: ', prop)
        print('base_url: ', base_url)
        print('current_url: ', current_url)
        print('base_api_url: ', base_api_url)

    api_url = request.base_url
    rdf_obj = Api(subject_uri=subject_uri,
                  data_class_uri=class_uri,
                  data_prop_uri=prop_uri,
                  rdf_field_list=[prop_json],
                  prop_list = [prop],
                  base_url=base_url, 
                  current_url=current_url,
                  base_api_url=base_api_url,
                  api_url=api_url)
    if request.method == "POST":
        save_result = rdf_obj.save()
        if debug: print("**** save_result:\n",pp.pformat(save_result.__dict__))
        if debug: print("END rdf_generic_api POST -------------------------\n")
        return jsonify(save_result.save_results[0])
    else:
        api_data = rdfw().get_obj_data(rdf_obj)
        if debug: print("\t**** api_data:\n",pp.pprint(api_data))
        if debug: print("END rdf_generic_api GET --------------------------\n")
        return json.dumps(api_data['obj_json'], indent=4) 
        
@rdfw_core.route("/api/form_lookup/<class_uri>/<prop_uri>",
                  methods=["GET"])
def rdf_lookup_api(class_uri, prop_uri):
    if not DEBUG:
        debug = False
    else:
        debug = True
    if debug: print("START rdf_lookup_api ----------------------------\n")
    return abort(400)
    referer = request.environ.get("HTTP_REFERER")
    form_function_path = url_for("app.rdf_class_forms",
                                 form_name="form_name",
                                 form_instance="form_instance")
    base_form_path = \
            form_function_path.replace("form_name/form_instance.html", "")
    form_path = referer[referer.find(base_form_path)+len(base_form_path):\
            ].replace('.html','')
    form_exists = rdfw().form_exists(form_path)
    if not form_exists:
        return abort(400)
    form_class = rdf_framework_form_factory(form_path)() 
    if debug: print("form_path: ",form_path)
    if debug: print("Source Form: ", referer)
    #if debug: print("form dict:\n", pp.pformat(form_class.__dict__))
    related_fields = []
    for fld in form_class.rdf_field_list:
        print(fld.__dict__,"\n")
        if fld.kds_classUri == class_uri:
            related_fields.append(fld)
        for _range in make_list(fld.rdfs_range):
            if _range.get("rangeClass") == class_uri:
                related_fields.append(fld)
        if fld.type == "FieldList":
            if fld.entries[0].type == "FormField":
                for _fld in fld.entries[0].rdf_field_list:
                    if class_uri == _fld.kds_classUri:
                        related_fields.append(_fld)
    for fld in related_fields:
        print("field: ",fld.name)
    subject_uri = request.args.get("id")
    data = request.args.get("dataValue")
    subject_uri = request.form.get("id",subject_uri)
    if debug: print("REQUEST dict: \n", pp.pformat(request.__dict__))
    rdf_class = getattr(rdfw(), class_uri)
    '''prop_json = rdf_class.kds_properties.get(prop_uri)
    prop_json['kds_classUri'] = class_uri
    prop_json['kds_apiFieldName'] = prop_uri
    prop = RdfProperty(prop_json, data, subject_uri)
    base_url = "%s%s" % (request.url_root[:-1], url_for("app.base_path")) 
    current_url = request.url
    base_api_url = "%s%sapi/form_generic_prop/" % (request.url_root[:-1],
                                   url_for("app.base_path"))
    if debug:
        print('subject_uri: ', subject_uri)
        print('data: ', data)
        print('rdf_class: ', rdf_class)
        print('prop_json: ', prop_json)
        print('prop: ', prop)
        print('base_url: ', base_url)
        print('current_url: ', current_url)
        print('base_api_url: ', base_api_url)

    api_url = request.base_url
    rdf_obj = Api(subject_uri=subject_uri,
                  data_class_uri=class_uri,
                  data_prop_uri=prop_uri,
                  rdf_field_list=[prop_json],
                  prop_list = [prop],
                  base_url=base_url, 
                  current_url=current_url,
                  base_api_url=base_api_url,
                  api_url=api_url)
    if request.method == "POST":
        save_result = rdf_obj.save()
        if debug: print("**** save_result:\n",pp.pformat(save_result.__dict__))
        if debug: print("END rdf_generic_api POST -------------------------\n")
        return jsonify(save_result.save_results[0])
    else:
        api_data = rdfw().get_obj_data(rdf_obj)
        if debug: print("\t**** api_data:\n",pp.pprint(api_data))
        if debug: print("END rdf_generic_api GET --------------------------\n")
        return json.dumps(api_data['obj_json'], indent=4) '''
        
@rdfw_core.route("/rdfjson/", methods=["POST", "GET"])
def form_rdf_class():
    '''View displays the RDF json'''
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
