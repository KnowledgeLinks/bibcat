__author__ = "Mike Stabile"

import os
from jinja2 import Environment, FileSystemLoader
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

def render_without_request(template_name, **template_vars):
    """
    Usage is the same as flask.render_template:

    render_without_request('my_template.html', var1='foo', var2='bar')
    """
    env = Environment(loader=FileSystemLoader(os.path.join(PROJECT_ROOT, "templates")))
    template = env.get_template(template_name)
    return template.render(**template_vars)
    
