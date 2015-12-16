__author__ = "Jeremy Nelson"

import os
import json
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
try:
    from flask_wtf import Form
    from flask_wtf.file import FileField
except ImportError:
    from wtforms import Form
    from wtforms.fields import FieldField
from wtforms.fields import BooleanField, DateTimeField, Field
from wtforms.fields import SelectField, StringField, TextAreaField
from wtforms.widgets import TextInput
import requests
from jinja2 import Environment, FileSystemLoader, PackageLoader
from datetime import datetime as datetime

def render_without_request(template_name, **template_vars):
    """
    Usage is the same as flask.render_template:

    render_without_request('my_template.html', var1='foo', var2='bar')
    """
    env = Environment(loader=FileSystemLoader(os.path.join(PROJECT_ROOT, "templates")))
    '''Environment(
        loader= PackageLoader('web/ebadges/badges','templates')
    )'''
    template = env.get_template(template_name)
    return template.render(**template_vars)
    


class CollectionListField(Field):
    """Form represents a comma-separate list of items"""
    widget = TextInput()

    def _value(self):
        if self.data:
            return ', '.join(self.data)
        else:
            return ''

    def process_formdata(self, valuelist):
        if valuelist:
            self.data = [x.strip() for x in valuelist[0].split(',')]
        else:
            self.data = []


class NewBadgeClass(Form):
    """Form for adding a new badge class"""
    name = StringField()
    description = TextAreaField()
    criteria = CollectionListField()
    endDate = DateTimeField("End Date")
    image_file = FileField("Upload Image File")
    image_url = StringField()
    tags = CollectionListField()
    startDate = DateTimeField("Start Date")


class NewAssertion(Form):
    """Form for adding a new Assertion"""
    badge = SelectField("Badge")
    email = StringField("Recipient email")
    familyName = StringField("Recipient family Name")
    givenName = StringField("Recipient given Name")
    issuedOn = DateTimeField("issuedOn", default=datetime.utcnow())


    