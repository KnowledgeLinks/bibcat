__author__ = "Jeremy Nelson"

from datetime import datetime as datetime

from wtforms import Form
from wtforms.fields import BooleanField, DateTimeField, Field, FileField 
from wtforms.fields import SelectField, StringField, TextAreaField
from wtforms.widgets import TextInput

class CollectionListField(Field):
    """Form represents a comma-separate list of items"""
    widget = TextInput()

    def _value(self):
        if self.data:
            return ', '.join(self.data)
        else:
            return ''

    def process_formdata(self, valuelist):
        print("In CollectionListField {}".format(valuelist))
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
