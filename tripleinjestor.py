"""viaf.org dump to graph database reference builder"""
__author__ = "Jeremy Nelson, Mike Stabile"

import os
import sys
import subprocess
import gzip
import datetime
import shutil
import requests

class TripleInjestor():
    ''' Class will take a large RDF file and send the data in batchs to the
        graph database '''
    
    def __init__(self, **kwargs):
        
        # test to make sure all the required kwargs are supplied
        required_kwargs = set(['filename', 'db_url'])
        missing_kwargs = required_kwargs - set(kwargs.keys())
        if len(missing_kwargs) > 0:
             raise MissingKwargs(missing_kwargs)
        self.graph_name = kwargs.get("graph_name")
        self.filename = kwargs.get("filename")
        self.db_url = kwargs.get("db_url")
        self.triple_count = 0
        self.batch_size = kwargs.get("batch_size",1000)
        self.batch_count = 0
        self.today = datetime.date.today()
        self.start_line = kwargs.get("start_line",1)
        self.temp_folder = kwargs.get("temp_folder","./triple_temp/")
        self._set_sys_os()
        
    def run(self):
        ''' reads the data file and sends the data to the database '''
        
        # read the triple data file and send to the database in the 
        # specified batch size
        
        self.start_time = datetime.datetime.now()
        
        # make sure the temp_folder exists
        self._action_temp_folder(action="reset")
        # create a file in the temp folder with batches of specified size
        self._make_batches()
        #self._write_batches()
        
    def _write_batches(self):
        ''' reads through the temp folder and sends the files to th db '''
        # test to see if the temp folder exists
        self._action_temp_folder()
        current_file = os.listdir
        
    def _make_batches(self):
        ''' cycles through the file and creates temporary files '''
        self._decompress()
        print("starting batch creation")
        if self.os == 'linux':
            print("Spliting file via linux command line.")
            result = subprocess.Popen(['split',
                                       '--lines',
                                       self.batch_size,
                                       self.filename,
                                       os.path.join(self.temp_folder, "batch_")
                                      ])
        elif "win" in str(self.os).lower():
            print('spliting via file read')
            batch = bytes()
            self.batch_count = 0
            line_count = 1
            with gzip.open(self.filename, 'r') as f:
                for line in f:
                    if self.triple_count >= self.start_line:
                        batch += line
                        if line_count >= self.batch_size:
                            line_count = 1
                            self._write_batch_file(batch)
                            batch = bytes()
                        else:
                            line_count += 1
                    self.triple_count += 1
            # send the remaining items to the database
            if len(batch) > 0:
                self._write_batch_file(batch)
    
    def _action_temp_folder(self, action="test"):
        ''' perform actions against the temp_folder '''
        delete_req = True
        # make sure the temp_folder exists
        if not os.path.isdir(self.temp_folder):
            delete_req = False
            os.mkdir(self.temp_folder)
        # if reset, delete the contents.
        if action == "reset" and delete_req:
            delete_dir(self.temp_folder, "preserve")
            
    def _send_to_db(self, batch):
        ''' sends the batch data to the database '''
        
        # set the params if the data is to be pushed to a graph
        params = {}
        self.batch_start = datetime.datetime.now()
        
        self.batch_count += 1
        
        if self.graph_name is not None:
            params = {"context-uri": self.graph_name}
        # send batch to database
        result = requests.post(url=self.db_url,
                               headers={"Content-Type": "text/turtle"},
                               params=params,
                               data=batch)
        if result.status_code > 399:
            batch_err_file = "batch_error_%s_%s.ttl" % \
                    (str(self.batch_count).zfill(3), self.today)
            f = open(batch_err_file, "wb")
            f.write(batch)
            f.close()
        self.batch_end = datetime.datetime.now()
        print("batch:\t%s\t%s\t%s" % (self.batch_end-self.batch_start,
                                      self.batch_end-self.start_time,
                                      self.triple_count))

    def _write_batch_file(self, batch):
        ''' writes the batch to a tempfile '''
        
        # set the params if the data is to be pushed to a graph
        self.batch_start = datetime.datetime.now()
        self.batch_count += 1
        print("writing batch file")
        # write batch file to temp folder
        temp_file = os.path.join(self.temp_folder,"batch_%s.temp" % \
                str(self.batch_count).zfill(10))
        f = open(temp_file,"wb")
        f.write(batch)
        f.close()
        
        self.batch_end = datetime.datetime.now()
        print("batch:\t%s\t%s\t%s" % (self.batch_end-self.batch_start,
                                      self.batch_end-self.start_time,
                                      self.triple_count))
                 
    def _set_sys_os(self):
        ''' sets the self.os attribute to windows, linux or OS X '''
        self.os = sys.platform
    
    def _decompress():
        ''' will decompress the file if it is compressed '''
        
            
        
        

class MissingKwargs(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return "Missing Kwargs -> %s" % repr(self.value)
        
def delete_dir(directory, action="preserve"):
    
    shutil.rmtree(directory)
    # wait for the directory to be deleted
    while os.path.exists(directory):
        pass
    if action == "preserve":
        os.mkdir(directory)
    