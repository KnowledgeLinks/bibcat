__author__ = "Mike Stabile, Jeremy Nelson"

"""
RDFframework
=======

RDFframework is a flexible application framework for implementing an 
application defined in a Resource Description Framework (RDF) data file that
is based on the http://knowledgelinks.io/ns/data-structures/ (kds) RDF 
vocabulary. 

:copyright: Copyright (c) 2016 by Michael Stabile and Jeremy Nelson.
:license: To be determined, see LICENSE.txt for details.
"""

from .getframework import get_framework
from .rdfclass import RdfClass
from .rdfdatatype import *
from .rdfproperty import *

__version__ = '0.0.1'