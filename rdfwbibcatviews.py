"""Flask Blueprint for bibcat unique views"""
__author__ = "Jeremy Nelson, Mike Stabile"

import time
import base64
import re
import io
import json
import requests
from urllib.request import urlopen
from werkzeug import wsgi
from flask import Flask, abort, Blueprint, jsonify, render_template, Response,\
        request, redirect, url_for, send_file, current_app
from flask.ext.login import login_required, login_user, current_user, \
        logout_user
from flask_wtf import CsrfProtect
from rdfframework import RdfProperty, get_framework as rdfw
from rdfframework.utilities import render_without_request, code_timer, \
        remove_null, pp, clean_iri, uid_to_repo_uri, cbool, make_list
from rdfframework.forms import rdf_framework_form_factory 
from rdfframework.api import rdf_framework_api_factory, Api
from rdfframework.security import User

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
