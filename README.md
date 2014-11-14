# Islandora.ca eBadges Repository

This Flask application allows the [Islandora.ca][ISLANDORA_CA] foundation to issue Camp, special
projects, and other types of [Open Badges][OPENBADGE]. Badge class
information and individually issued badge images are stored in a [Fedora 4][FEDORA] digital
repository.

## Introduction
The [Islandora.ca][ISLANDORA_CA] eBadges Repository application provides a 
light-weight web front-end for issuing and hosting [Open Badges][OPENBADGE] by the
Islandora Foundation and possible use by other organizations.

## Installation
To install this application, you'll need to install [Python 3][PY3]. Using a
[virtualenv][VRTENV] to isolate your Python environment from the OS version is 
highly recommended.

### Using PIP
This application is available on https://pypi.python.org/ and can be installed
from the command-line:

`$ pip install IslandoraOpenBadges`  

### From source
To install and use the application from source, 

1.  Clone the repository from github

    `$ git clone https://github.com/Islandora/Islandora-eBadges-Repository.git`

1.  Run setup.py to install

    `$ cd Islandora-eBadges-Repository`
    `$ python setup.py install`

## Configuration
This application requires the following variables to be set prior to running;  
An **application.cfg** needs be
created in the root directory. This application is a simple text file with the
following configuration variables, one per line:

    BADGE_ISSUER_NAME = 'Islandora Foundation'
    BADGE_ISSUER_URL = 'http://islandora.ca'
    FEDORA_BASE_URL = 'http//localhost:8080'

## Usage
To run the front-end web application in debug mode using the built-in development
web server, run the following command:

`$ python badges.py serve --host 0.0.0.0 --port 8100`

To create a badge and then issue that badge to individuals requires a running  
two commands. 

### Create a Badge Class
Run the following command and answer the prompts to create a Badge Class:

`python badges.py new` 

### Issue an Badge  
To issue an [Open Badge][OPENBADGE] to an individual that has registered their
email address and created an [Mozilla Backpack](http://backpack.openbadges.org/)
account, run the following:

`$ python badges.py issue --email holly@example.com --badge IslandoraCampCO`

This will return an URL to the issued badge PNG image that the user can then
upload to their backpack.

[FEDORA]: http://fedora-commons.org/
[ISLANDORA_CA]: http://islandora.ca/
[OPENBADGE]: http://openbadges.org/
[PY3]: https://www.python.org/
[VRTENV]: http://virtualenv.readthedocs.org/
