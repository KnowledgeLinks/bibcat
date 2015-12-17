__author__ = "Jeremy Nelson, Mike Stabile"

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
import wtforms.form
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


def getFormField(field):
    form_field = None
    if field['fieldType'] in ['text', 'email', 'password']:
        form_field = StringField(field.get('formLabelName',field['formFieldName']))
    elif field['fieldType'] == 'serverOnly':
        form_field = "serverVar"
    elif field['fieldType'] == 'textarea':
        form_field = TextAreaField(field.get('formLabelName',field['formFieldName']))
    elif field['fieldType'] == 'boolean':
        form_field = BooleanField(field.get('formLabelName',field['formFieldName']))
    elif field['fieldType'] == 'file':
        form_field = FileField(field.get('formLabelName',field['formFieldName']))
    elif field['fieldType'] == 'date':
        form_field = DateField(field.get('formLabelName',field['formFieldName']))
    elif field['fieldType'] == 'dateTime':
        form_field = DateTimeField(field.get('formLabelName',field['formFieldName']))
    elif field['fieldType'] in ['lookup', 'valueList', 'image']:
        form_field = ""
    return form_field 
     
def rdf_form_factory(name,
                     object_class, 
                     triplestore_url="http://localhost:8080/bigdata/sparql"):
    rdf_form = type(name, (Form, ), {})
    sparql = render_without_request(
        "jsonFormQueryTemplate.rq",
        object_class = object_class) 
    fieldList =  requests.post( 
        triplestore_url,
        data={"query": sparql,
              "format": "json"})
    fields = json.loads(fieldList.json().get('results').get('bindings')[0]['jsonString']['value'])
    for field in fields:
        form_field = getFormField(field)
        if form_field:
            setattr(rdf_form, field['formFieldName'], form_field)
    return rdf_form
