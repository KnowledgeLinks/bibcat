import requests
from rdfframework import RdfDataType
from rdfframework.utilities import make_triple, iri, clean_iri, fw_config
__author__ = "Mike Stabile, Jeremy Nelson"

class UniqueValue(object):
    ''' a custom validator for use with wtforms
        * checks to see if the value already exists in the triplestore'''

    def __init__(self, message=None):
        if not message:
            message = u'The field must be a unique value'
        self.message = message

    def __call__(self, form, field):
        # get the test query
        _sparql = self._make_unique_value_qry(form, field)
        print(_sparql)
        # run the test query
        _unique_test_results = requests.post(\
                fw_config().get('TRIPLESTORE_URL'),
                data={"query": _sparql, "format": "json"})
        _unique_test = _unique_test_results.json().get('results').get( \
                            'bindings', [])
        # evaluate the results; True result in the query denotes that the
        # value already exists
        if len(_unique_test) > 0:
            _unique_test = _unique_test[0].get(\
                    'uniqueValueViolation', {}).get('value', False)
        else:
            _unique_test = False
        if _unique_test:
            raise ValidationError(self.message)


    def _make_unique_value_qry(self, form, field):
        _sparql_args = []
        # determine the property and class details of the field
        for _row in form.rdfFieldList:
            for _field in _row:
                if _field.get('formFieldName') == field.name:
                    _prop_uri = _field.get("propUri")
                    _class_uri = _field.get("classUri")
                    _class_name = get_framework().get_class_name(_class_uri)
                    _range = _field.get("range")
                    break
        # make the base triples for the query
        if _prop_uri:
            _data_value = RdfDataType(None,
                                      class_uri=_class_uri,
                                      prop_uri=_prop_uri).sparql(field.data)
            _sparql_args.append(make_triple("?uri", "a", iri(_class_uri)))
            _sparql_args.append(make_triple("?uri",
                                            iri(_prop_uri),
                                            _data_value))
        # see if the form is based on a set of triplestore data. if it is
        # remove that triple from consideration in the query
        if hasattr(form, "dataSubjectUri"):
            _subject_uri = form.dataSubjectUri
            _lookup_class_uri = form.dataClassUri
            # if the subject class is the same as the field class
            if _lookup_class_uri == _class_uri and _subject_uri:
                _sparql_args.append("FILTER(?uri!={}) .".format(\
                        iri(_subject_uri)))
            # If not need to determine how the subject is related to the field
            # property
            elif _subject_uri:
                _lookup_class_name = get_framework().get_class_name(\
                        _lookup_class_uri)
                # class links shows the relationship between the classes in a form
                _class_links = get_framework().get_form_class_links(form).get(\
                        "dependancies")
                # cycle through the class links to find the subject linkage
                for _rdf_class in _class_links:
                    for _prop in _class_links[_rdf_class]:
                        if _lookup_class_uri == _prop.get("classUri"):
                            _linked_lookup_class_name = _rdf_class
                            _linked_lookup_prop = _prop.get("propUri")
                            break
                # if there is a direct link between the subject class and
                # field class add the sparql arguments
                if _linked_lookup_class_name == _class_name:
                    _sparql_args.append(\
                            "OPTIONAL{{?uri {} ?linkedUri}} .".format(\
                                    iri(_linked_lookup_prop)))
                else:
                    # find the indirect linkage i.e.
                    #    field in class A that links to class B with a lookup
                    #    subject in class C
                    for _rdf_class in _class_links:
                        for _prop in _class_links[_rdf_class]:
                            if _class_uri == _prop.get("classUri"):
                                _linked_field_class_name = _rdf_class
                                _linked_field_prop = _prop.get("propUri")
                                break
                    if _linked_lookup_class_name == _linked_field_class_name:
                        _sparql_args.append("OPTIONAL {")
                        _sparql_args.append("?pass {} ?uri .".format(\
                                iri(_linked_field_prop)))
                        _sparql_args.append("?pass {} ?linkedUri .".format(\
                                iri(_linked_lookup_prop)))
                        _sparql_args.append("} .")
                _sparql_args.append(\
                        "BIND(IF(bound(?linkedUri),?linkedUri,'') AS ?link)")
                _sparql_args.append("FILTER(?link!={}).".format(\
                        iri(_subject_uri)))
        return '''{}\nSELECT (COUNT(?uri)>0 AS ?uniqueValueViolation)
{{\n{}\n}}\nGROUP BY ?uri'''.format(get_framework().get_prefix(),
                                    "\n\t".join(_sparql_args))
