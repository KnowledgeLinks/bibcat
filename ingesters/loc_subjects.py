"""Loc Subject heading to BIBFRAME 2.0 converter

The loc subjects data file on the loc website does not have any
associated bibrame vocabulary. This module will perform the following steps:
    1. download the data file from loc site
    2. upload the file to the triplestore
    3. run SPARQL update queires to add bibframe vocabulary
    4. Save the augmented data to a file in rdf-references folder
    5. Push the data to elasticsearch
"""
__author__ = "Jeremy Nelson, Mike Stabile"

import datetime
import inspect
import logging
import os
import rdflib
import requests
import sys
import uuid
import pdb
import urllib
import time
import queue
import threading
import json
import socket

from os.path import expanduser
HOME = expanduser("~")
# get the current file name for logs and set logging levels
try:
    MNAME = inspect.stack()[0][1]
except:
    MNAME = "loc_subjects"
MLOG_LVL = logging.DEBUG
logging.basicConfig(level=logging.DEBUG)
lg_r = logging.getLogger("requests")
lg_r.setLevel(logging.CRITICAL)
BASE_PATH = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]
sys.path.append(BASE_PATH)
try:
    from instance import config
except ImportError:
    sys.path.append(os.path.split(BASE_PATH)[0])
    from instance import config
try:
    from ingesters.ingester import NS_MGR as NSM
except ImportError:
    from .ingester import NS_MGR as NSM
from dateutil.parser import parse as date_parse
from rdfframework.utilities import mod_git_ignore, DataStatus, iri, pp, \
        convert_spo_to_dict, convert_obj_to_rdf_namespace, convert_spo_nested
from rdfframework.sparql import run_sparql_query, get_all_item_data
from rdfframework.search import EsBase
logging.basicConfig(level=logging.DEBUG)
PREFIX = NSM.prefix

ADD_TOPIC_TYPE_LOC_SUBJECTS = """
# Add bf:Topic type to each loc subject
INSERT
{
  ?s a bf:Topic
}
WHERE
{
  ?s skos:inScheme <http://id.loc.gov/authorities/subjects> .
}"""

ADD_IDENTIFIEDBY_LOC_SUBJECTS = """
# add a bf:identifiedBy property to each subject
INSERT
{
  ?s bf:identifiedBy _:sh .
   _:sh a bf:LCSH .
   _:sh rdf:value ?lcsh .
}

WHERE
{
  ?s skos:inScheme <http://id.loc.gov/authorities/subjects> .
  bind(REPLACE(STR(?s),  "^(.*[/])", "") as ?lcsh)
}"""

LOC_SUBJ_QUERIES = [ADD_TOPIC_TYPE_LOC_SUBJECTS, ADD_IDENTIFIEDBY_LOC_SUBJECTS]

lg = logging.getLogger("elasticsearch")
lg.setLevel(logging.CRITICAL)
lg = logging.getLogger("urllib3")
lg.setLevel(logging.CRITICAL)
class LocSubjectConverter(object):
    """ Reads the Loc subject source file and adds bibframe vocabulary to the 
    graph and pushes data to elasticsearch """

    ln = "%s-LocSubjectConverter" % MNAME
    log_level = logging.DEBUG

    def __init__(self):
        lg = logging.getLogger("%s.%s" % (self.ln, inspect.stack()[0][3]))
        lg.setLevel(self.log_level)
        lg.debug(" *** Started")
        self.data_status = DataStatus("locSubjects")
        self.local_file_name = 'loc_subjects_skos.nt.gz'
        #self.local_data_path = os.path.join(BASE_PATH, "local_data")
        self.local_data_path = os.path.join(HOME, "local_data")
        self.local_file_path = os.path.join(self.local_data_path,
                                            self.local_file_name)
        self.web_subj_url = config.DATASET_URLS[self.local_file_name]
        self.es_worker = EsBase(es_index="reference",
                                doc_type="topic")
        self.es_worker.create_index(reset_index=True)
        self._check_new_subjects_file()
        self._load_subjects_to_db()
        self.count = 0
        if self.new_subjects:
            self._convert_to_bibframe()
        self._index_subjects()


    def _check_new_subjects_file(self):
        """ Checks if there is a new subjects file posted, downloads it
        if there is one. 

        Args:
            None
        """
        lg = logging.getLogger("%s.%s" % (self.ln, inspect.stack()[0][3]))
        lg.setLevel(self.log_level)
        lg.debug("checking for new subjects file")
        # get the file info from the loc web site
        try:
            loc_web = urllib.request.urlopen(self.web_subj_url)
            loc_file_date = date_parse(loc_web.info()['Last-Modified'])
        # if not connected to the internt of internet file not available
        # set the date to far in the past
        except:
            loc_file_date = datetime.datetime(2000, 
                                              1, 
                                              1, 
                                              1, 
                                              1, 
                                              tzinfo=datetime.timezone.utc)


        # verify a local data path exits
        if not os.path.isdir(self.local_data_path):
            os.makedirs(self.local_data_path)
        # ensure the .gitignore file contains the local data path
        mod_git_ignore(directory=BASE_PATH, 
                       action="add", 
                       ignore_item="local_data/")

        if os.path.exists(self.local_file_path):
            timestamp = os.path.getmtime(self.local_file_path)
            local_mod_time = datetime.datetime.fromtimestamp(\
                    time.mktime(time.gmtime(timestamp)),
                    tz=datetime.timezone.utc)
        else:
            local_mod_time = None
        if local_mod_time and local_mod_time > loc_file_date:
            self.new_file = False
            lg.debug("current file already downloaded")
        else:
            lg.info("Downloading loc subject file")
            urllib.request.urlretrieve(self.web_subj_url, self.local_file_path)
            self.new_file = True

    def _load_subjects_to_db(self):
        """ loads the loc_subjects triples into the database if required """
        # Test to see if the loc_subjects data has been loaded
        lg = logging.getLogger("%s.%s" % (self.ln, inspect.stack()[0][3]))
        lg.setLevel(self.log_level)
        
        if not self.data_status.get("loaded") or self.new_file:
            # drop the locsubject graph
            lg.info("dropping loc subject graph")
            stmt = "DROP GRAPH %s;" % config.RDF_LOC_SUBJECT_GRAPH
            drop_extensions = requests.post(
                url=config.TRIPLESTORE_URL,
                params={"update": stmt})
            lg.info("loading Loc Subjects graph to the triplestore")
            # load the subjects graph to the db
            data = "file:///local_data/%s" % self.local_file_name
            result = requests.post(
                    url=config.TRIPLESTORE_URL,
                    params={"context-uri": config.RDF_LOC_SUBJECT_GRAPH,
                            "uri": data})   
            lg.info("loc subjects loaded")
            # mark the database that is has been loaded
            self.data_status.set("loaded", True)
            self.new_subjects = True
        else:
            lg.info("subjects already loaded")
            self.new_subjects = False

    def _convert_to_bibframe(self):
        """ Converts the raw loc triples to bibframe vocab """
        lg = logging.getLogger("%s.%s" % (self.ln, inspect.stack()[0][3]))
        lg.setLevel(self.log_level)
        for query in LOC_SUBJ_QUERIES:
            lg.info("*** Running:\n%s", query)
            result = requests.post(config.TRIPLESTORE_URL,
                                   data={"update":NSM.prefix() + query}) 
        lg.info("*** Finished converting subjects")

    def _index_subjects(self):
        """ quereies the triplestore for all subject uri"""

        lg = logging.getLogger("%s.%s" % (self.ln, inspect.stack()[0][3]))
        lg.setLevel(self.log_level)

        # if the subjects have been indexed and there are no new subjects exit
        if self.data_status.get("indexed") and not self.new_subjects:
            return
        # get a list of all the loc_subject URIs
        sparql = """
            SELECT ?s 
            {
                ?s skos:inScheme <http://id.loc.gov/authorities/subjects> .
            }"""
        results = run_sparql_query(sparql=sparql)
        # Start processing through
        self.time_start = datetime.datetime.now()
        batch_size = 12000
        if len(results) > batch_size:
            batch_end = batch_size
        else:
            batch_end = len(results) - 1
        batch_start = 0
        batch_num = 1
        self.batch_data = {}
        self.batch_data[batch_num] = []
        end = False
        last = False
        while not end:
            lg.debug("batch %s: %s-%s", batch_num, batch_start, batch_end)
            for i, subj in enumerate(results[batch_start:batch_end]):
                th = threading.Thread(name=batch_start + i + 1,
                                      target=self._index_subject_item,
                                      args=(iri(subj['s']['value']),
                                            i+1,batch_num,))
                th.start()
                #self._index_subject_item(iri(subj['s']['value']),i+1)
            print(datetime.datetime.now() - self.time_start)
            main_thread = threading.main_thread()
            for t in threading.enumerate():
                if t is main_thread:
                    continue
                #print('joining %s', t.getName())
                t.join()
            action_list = \
                    self.es_worker.make_action_list(self.batch_data[batch_num])
            self.es_worker.bulk_save(action_list)
            del self.batch_data[batch_num]
            batch_end += batch_size
            batch_start += batch_size
            if last:
                end = True
            if len(results) <= batch_end:
                batch_end = len(results)
                last = True
            batch_num += 1
            self.batch_data[batch_num] = []
            print(datetime.datetime.now() - self.time_start)

    def _index_subject_item(self, uri, num, batch_num):
        """ queries the triplestore for an item sends it to elasticsearch """

        #print("Thread %s - start" % num)
        data = get_all_item_data(uri)
        # new_item = convert_obj_to_rdf_namespace(\
        #         obj=convert_spo_nested(data, uri),
        #         key_only=True)
        self.batch_data[batch_num].append(convert_obj_to_rdf_namespace(\
                obj=convert_spo_nested(data, uri),
                key_only=True))
        self.count += 1
        #self.es_worker.save(data=new_item, id_field="id")
        #print("Thread %s, count %s" % (num, self.count))

from rdfframework.sparql import get_class_def_item_data as gd, get_linker_def_item_data as gl
import rdfframework.utilities as ut
df = gd("schema:Muscian")
ld = gl()
d1 = ut.convert_spo_to_dict(ld)
#print(json.dumps(ut.convert_obj_to_rdf_namespace(d1), indent=4))
spolg = logging.getLogger("spo")
spolg.setLevel(logging.DEBUG)
spolg.addHandler(logging.FileHandler(filename="spo.log", mode="w"))
spolg.debug("******\n%s",json.dumps(ut.convert_obj_to_rdf_namespace(d1),indent=4))
#d0 = ut.convert_spo_def(df, "bf:Topic")
d0 = ut.convert_ispo_to_dict(df, base="schema:Muscian")

pdb.set_trace()
