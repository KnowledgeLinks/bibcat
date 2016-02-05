__author__ = "Mike Stabile"

import os
from jinja2 import Environment, FileSystemLoader
FRAMEWORK_BASE = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

ENV = Environment(loader=FileSystemLoader(
    [os.path.join(FRAMEWORK_BASE, "sparql"),
     os.path.join(FRAMEWORK_BASE, "turtle")]))


def render_without_request(template_name, **template_vars):
    """
    Usage is the same as flask.render_template:

    render_without_request('my_template.html', var1='foo', var2='bar')
    """
    template = ENV.get_template(template_name)
    return template.render(**template_vars)
    
