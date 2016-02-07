__author__ = "Mike Stabile, Jeremy Nelson"

from wtforms.widgets import HTMLString

class BsGridTableWidget(object):
    """
    Renders a list of fields as a bootstrap formated table.

    If `with_row_tag` is True, then an enclosing <row> is placed around the
    rows.

    Hidden fields will not be displayed with a row, instead the field will be
    pushed into a subsequent table row to ensure XHTML validity. Hidden fields
    at the end of the field list will appear outside the table.
    """
    def __init__(self, with_section_tag=False):
        self.with_section_tag = with_section_tag

    def __call__(self, field, **kwargs):
        html = []
        if self.with_section_tag:
            kwargs.setdefault('id', field.id)
            html.append('<section class="col-md-6" %s>' % html_params(**kwargs))
        hidden = ''
        _params = html_params(**kwargs)
        for subfield in field:
            if subfield.type == 'CSRFTokenField':
                html.append('<div style="display:none" %s>%s</div>' % (_params,text_type(subfield(class_="form-control"))))
            else:
                html.append('<div class="col-md-2" %s>%s</div>' % (_params,text_type(subfield(class_="form-control"))))
                hidden = ''
        if self.with_section_tag:
            html.append('</section>')
        if hidden:
            html.append(hidden)
        return HTMLString(''.join(html))

class RepeatingSubFormWidget(object):
    """
    Renders a list of fields as a `row` list.

    This is used for fields which encapsulate many inner fields as subfields.
    The widget will try to iterate the field to get access to the subfields and
    call them to render them.

    If `prefix_label` is set, the subfield's label is printed before the field,
    otherwise afterwards. The latter is useful for iterating radios or
    checkboxes.
    """
    def __init__(self, html_tag='div', prefix_label=True):
        assert html_tag in ('ol', 'ul', 'div')
        self.html_tag = html_tag
        self.prefix_label = prefix_label

    def __call__(self, field, **kwargs):
        kwargs.setdefault('id', field.id)
        _params = html_params(**kwargs)
        html = []
        html.append('<%s class="row">' % (self.html_tag))
        for sub_subfield in field[0]:
            if sub_subfield.type != 'CSRFTokenField':
                html.append('<div class="col-md-2">%s</div>' % sub_subfield.label)
        html.append('</%s>' % (self.html_tag))    
        for subfield in field:
            html.append('<%s class="row">%s</%s>' % (self.html_tag,
                                           #_params,
                                           subfield(),
                                           self.html_tag))
        return HTMLString(''.join(html))

