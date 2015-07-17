@badge_app.route("/badges/<badge>/<uid>")
@badge_app.route("/badges/<badge>/<uid>.json")
#@produces('application/json')
def badge_assertion(badge, uid):
    """Route returns individual badge assertation json or 404 error if not
    found in the repository.

    Args:
        event: Badge Type (Camp, Projects, Institutions, etc.)
        uid: Unique ID of the Badge

    Returns:
        Assertion JSON of issued badge
    """
    result = requests.post(TRIPLESTORE_URL,
        data={"sparql": FIND_ASSERTION_SPARQL.format(uid)})
    if result.status_code > 399:
        abort(400)
    bindings = result.json().get('results').get('bindings')
    if len(bindings) < 1:
        abort(404)
    badge_graph = rdflib.Graph().parse(badge_uri)
    issuedOn = datetime.strptime(
        bindings[0]['IssuedOne']['value'],
        "%Y-%m-%dT%H:%M:%S.%f")             
    badge = {
        "uid": uid,
        "recipient": bindings[0]['recipient']['value'],
        "badge": url_for('badge_class', badge_classname=badge),
        "image": url_for('badge_image', badge=badge, uid=uid),
        "issuedOn": int(time.mktime(issuedOn.timetuple())),
        "verify": {
            "type": "hosted",
            "url": "{}.json".format(
                url_for('badge_assertion', badge=badge, uid=uid))
        }
    }
    return jsonify(badge)

@badge_app.route("/badges/<badge>.png")
@badge_app.route("/badges/<badge>/<uid>.png")
def badge_image(badge, uid=None):
    if uid is not None:
        # Specific Issued Badge
        result = requests.post(
            TRIPLESTORE_URL,
            data={"sparql": FIND_IMAGE_SPARQL.format(uid)})
    else:
        # Badge Class Image
        result = requests.post(
            TRIPLESTORE_URL,
            data={"sparql": FIND_CLASS_IMAGE_SPARQL.format(badge)})
    if result.status_code > 399:
        abort(400)
    bindings = result.json().get('results').get('bindings')
    if len(bindings) < 1:
        abort(404)       
    img_url = bindings[0]['image']['value']
    img = urllib.request.urlopen(img_url).read()
    return Response(img, mimetype='image/png')

@badge_app.route("/badges/<badge_classname>")
@badge_app.route("/badges/<badge_classname>.json")
@produces('application/json', 'application/rdf+xml', 'text/html')
def badge_class(badge_classname):
    """Route generates a JSON BadgeClass
    <https://github.com/mozilla/openbadges-specification/> for each Islandora
    badge.

    Args:
        badge_classname: Name of Badge (Camp, Projects, Institutions, etc.)

    Returns:
        Badge Class JSON
    """
    result = requests.post(
        TRIPLESTORE_URL,
        data={"sparql": FIND_CLASS_SPARQL.format(badge_classname)})
    if result.status_code > 399:
        abort(400)
    bindings = result.json().get('results').get('bindings')
    if len(bindings) < 1:
        abort(404)
    info = bindings[0]
    keyword_result = requests.post(
       TRIPLESTORE_URL,
       data={"sparql": """{}
SELECT DISTINCT ?keyword
WHERE {{
  ?subject schema:alternativeName "{}"^^xsd:string .
  ?subject schema:keywords ?keyword .
}}""".format(PREFIX, badge_classname)})
    keywords = []
    if keyword_result.status_code < 400:
        for row in keyword_result.json().get('results').get('bindings'):
            keywords.append(row['keyword']['value'])
    badge_class_json = {
        "name": info.get('name').get('value'),
        "description": info.get('description').get('value'),
        "critera": url_for('badge_criteria', badge=badge_classname),
        "image": url_for('badge_image', badge=badge_classname),
        "issuer": url_for('badge_issuer_organization'),
        "tags": keywords
        }
    return jsonify(badge_class_json)

@badge_app.route("/badges/<badge>/criteria")
def badge_criteria(badge):
    """Route displays the criteria for the badge class

    Args:
        badge: Name of Badge (Camp, Projects, Institutions, etc.)

    Returns:
        JSON of badge's critera
    """
    badge_result = requests.post(
        TRIPLESTORE_URL,
        data={"sparql": FIND_CRITERIA_SPARQL.format(badge)})
    if badge_result.status_code > 399:
        abort(400)
    bindings = badge_result.json().get('results').get('bindings')
    if len(bindings) < 1:
        abort(404)
    name ="Criteria for {} Open Badge".format(bindings[0]['name']['value']) 
    badge_criteria = {
        "name": name,
        "educationalUse": [row.get('criteria').get('value') for row in bindings]
    }
    return jsonify(badge_criteria)

@badge_app.route("/badges/issuer")
def badge_issuer_organization():
    "Route generates JSON for the badge issuer's organization"
    organization = {
        "name": badge_app.config.get('BADGE_ISSUER').get('name'),
        "url": badge_app.config.get('BADGE_ISSUER').get('url')
    }
    return jsonify(organization)

@badge_app.route("/")
def index():
    return render_template('index.html')

