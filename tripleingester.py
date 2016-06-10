"""viaf.org dump to graph database reference builder"""
__author__ = "Jeremy Nelson, Mike Stabile"

import os
import sys
import subprocess
import gzip
import datetime
import shutil
import pprint
import logging
import inspect
import requests

# set the modulename
mname = inspect.stack()[0][1]

#logging.basicConfig(level=logging.INFO)
pp = pprint.PrettyPrinter(indent=2)

class TripleIngester():
    """ Class will take a large RDF file and send the data in batchs to the
    graph database. This will be done either by splitting a file into smaller
    files or reading the file line by line and sending it in batches 
        
        * denotes required
        :kwarg db_url: * The url to the SPARQL endpoint
        :batch_size: The number of lines to send at a time
        :kwarg filename: path + filename of the file to injest
        :start_line: The line to start on when reading a file
        :temp_folder: Folder path for storing temporary files
        :completed_folder: Folder path to move completed temporary files
    """
    # set the classname
    ln = "%s-TirpleIngester" % mname
    # set specific logging handler for the module allows turning on and off
    # debug as required
    log_level = logging.DEBUG
    
    def __init__(self, **kwargs):
        # setup logger
        lg = logging.getLogger("%s-%s" % (self.ln, inspect.stack()[0][3]))
        lg.setLevel(self.log_level)
        
        lg.debug("\n***kwargs:\n%s",kwargs)
        # test to make sure all the required kwargs are supplied
        check_kwargs(kwargs, 'db_url')
        self.graph_name = kwargs.get("graph_name")
        self.filename = kwargs.get("filename")
        self.db_url = kwargs.get("db_url")
        self.start_line = kwargs.get("start_line",1)
        self.temp_folder = kwargs.get("temp_folder","./batch/")
        self.completed_folder = kwargs.get("completed_folder","./completed/")
        self.triple_count = 0
        self.batch_count = 0
        self.today = datetime.date.today()
        self._set_sys_os()
        lg.debug(log_attrs(self))
        
    def run(self):
        """ reads the data file and sends the data to the database """
        lg = logging.getLogger("%s-%s" % (self.ln, inspect.stack()[0][3]))
        lg.setLevel(self.log_level)
        # read the triple data file and send to the database in the 
        # specified batch size
        lg.debug("---START")
        self.start_time = datetime.datetime.now()
        
        # make sure the temp_folder exists
        #self._action_temp_folder(action="reset")
        # create a file in the temp folder with batches of specified size
        #self._make_batches()
        self._write_batches()
        lg.debug("---FINISH")
        
    def _write_batches(self):
        """ reads through the temp folder and sends the files to th db """
        lg = logging.getLogger("%s-%s" % (self.ln, inspect.stack()[0][3]))
        lg.setLevel(self.log_level)
        
        # test to see if the temp and completed folder exist and create if 
        # needed
        self._action_folder(self.temp_folder)
        self._action_folder(self.completed_folder)
        
        batches = []
        # get all of the files containing batches
        for (dirpath, dirnames, filenames) in os.walk(self.temp_folder):
            batches.extend(filenames)
            break
        lg.debug("STARTING batch writing")
        for batch in batches:
            lg.debug("batch file: %s", batch)
            data_file = open(os.path.join(self.temp_folder,batch),"r")
            batch_data = data_file.read()
            data_file.close()
            result = self._send_to_db(batch_data)
            if result != 'fail':
                os.rename(os.path.join(self.temp_folder,batch),
                          os.path.join(self.completed_folder,batch))
                   
    def _make_batches(self):
        """ cycles through the file and creates temporary files """
        lg = logging.getLogger("%s-%s" % (self.ln, inspect.stack()[0][3]))
        lg.setLevel(self.log_level)
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
    
    def _action_folder(self, folder, action="test"):
        """ perform actions against the temp_folder """
        lg = logging.getLogger("%s-%s" % (self.ln, inspect.stack()[0][3]))
        lg.setLevel(self.log_level)
        
        lg.debug("folder: %s - action: %s", folder, action)
        delete_req = True
        # make sure the temp_folder exists
        if not os.path.isdir(folder):
            lg.debug("\t%s folder does not exist - CREATING NOW!", folder)
            delete_req = False
            os.mkdir(folder)
        # if reset, delete the contents.
        if action == "reset" and delete_req:
            log.warn("\t*** Deleteing %s folder", folder)
            delete_dir(folder, "preserve")
            
    def _send_to_db(self, batch):
        """ sends the batch data to the database """
        lg = logging.getLogger("%s-%s" % (self.ln, inspect.stack()[0][3]))
        lg.setLevel(self.log_level)
        # set the params if the data is to be pushed to a graph

        self.batch_start = datetime.datetime.now()     
        self.batch_count += 1
        params = {}
        if self.graph_name is not None:
            params = {"context-uri": self.graph_name}
        # send batch to database
        result = requests.post(url=self.db_url,
                               headers={"Content-Type": "text/x-nquads"},
                               #params=params,
                               data=batch)
                               
        if result.status_code > 399:
            return "fail"
            batch_err_file = "batch_error_%s_%s.ttl" % \
                    (str(self.batch_count).zfill(3), self.today)
            f = open(batch_err_file, "wb")
            f.write(batch)
            f.close()
        self.batch_end = datetime.datetime.now()
        print("batch:\t%s\t%s\t%s" % (self.batch_end-self.batch_start,
                                      self.batch_end-self.start_time,
                                      self.batch_count))

    def _write_batch_file(self, batch):
        """ writes the batch to a tempfile """
        lg = logging.getLogger("%s-%s" % (self.ln, inspect.stack()[0][3]))
        lg.setLevel(self.log_level)
        # set the params if the data is to be pushed to a graph
        self.batch_start = datetime.datetime.now()
        self.batch_count += 1
        lg.debug("writing batch file -> %s", batch)
        # write batch file to temp folder
        temp_file = os.path.join(self.temp_folder,"batch_%s.temp" % \
                str(self.batch_count).zfill(10))
        f = open(temp_file,"wb")
        f.write(batch)
        f.close()
        
        self.batch_end = datetime.datetime.now()
        lg.debug("batch:\t%s\t%s\t%s" % (self.batch_end-self.batch_start,
                                         self.batch_end-self.start_time,
                                         self.triple_count))
                 
    def _set_sys_os(self):
        """ sets the self.os attribute to windows, linux or OS X """
        lg = logging.getLogger("%s-%s" % (self.ln, inspect.stack()[0][3]))
        lg.setLevel(self.log_level)
        
        self.os = sys.platform
        lg.debug("system os: %s", self.os)
        
    def _decompress():
        """ will decompress the file if it is compressed """
                    
        
def check_kwargs(kwargs, required):
    """ Checks to see if all kwargs are supplied and raises a MissingKwargs
        error if required kwargs are not supplied 
        
        :arg kwargs: the function/method's kwargs
        :arg required: list of required kwargs
        
    """        
    if not isinstance(required, list):
       required = [required]
    required_kwargs = set(required)
    missing_kwargs = required_kwargs - set(kwargs.keys())
    if len(missing_kwargs) > 0:
         raise MissingKwargs(missing_kwargs)

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

def log_attrs(class2log):
    """ Reads through a classes atributes and returns a string of the 
        attributes and their values.
        
        :arg class2log: The class to read
    """
    # start the logger
    lg = logging.getLogger("%s-%s" % (inspect.stack()[0][1], 
                                      inspect.stack()[0][3]))
    lg.setLevel(logging.INFO)
    
    # format the attributes for the class
    rtn_list = []
    for attr in class2log.__dict__:
        rtn_list.append("\t%s   ->   %s" % (attr, str(getattr(class2log,attr))))
        lg.debug("%s\t%s", attr, getattr(class2log,attr))
    return "\n***Class attributes:\n%s" % "\n".join(rtn_list)
    
if __name__ == "__main__":
    """ runs the ingester """
    logging.basicConfig(level=logging.DEBUG)
    
    logging.info("Running *** %s *** from command line",
                  inspect.stack()[0][1])

    ingester = TripleIngester( \
            db_url="http://stadeskserver:9999/blazegraph/sparql")
    ingester.run()
    
    

    