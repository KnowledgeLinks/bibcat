__author__ = "Jeremy Nelson"

from wtforms import Form
from wtforms.fields import BooleanField, DateTimeField, Field, FileField 
from wtforms.fields import StringField, TextField
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
        if valuelist:
            self.data = [x.strip() for x in valuelist[0].split(',')]
        else:
            self.data = []


class NewBadgeClass(Form):
    """Form for adding a new badge class"""
    name = StringField()
    description = TextField()
    criteria = CollectionListField()
    endDate = DateTimeField("End Date")
    image_file = FileField("Upload Image File")
    image_url = StringField()
    tags = CollectionListField()
    startDate = DateTimeField("Start Date")
