"""Basic User Class for Badge Application"""
from flask.ext.login import UserMixin

class User(UserMixin):

    def __init__(self, **kwargs):
        self.username = kwargs.get('user')
        self.password = kwargs.get('password')

    def get_id(self):
        return self.username

    def is_active(self):
        return True

    def is_anonymouse(self):
        return False

    def is_authenticated(self):
        return True
