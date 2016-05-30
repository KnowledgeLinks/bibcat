"""viaf.org dump to graph database reference builder"""
__author__ = "Jeremy Nelson, Mike Stabile"

import gzip
import requests
import datetime


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
        
    def run(self):
        ''' reads the data file and sends the data to the database '''
        
        # read the triple data file and send to the database in the 
        # specified batch size
        self.start_time = datetime.datetime.now()
        batch = bytes()
        line_count = 1
        with gzip.open(self.filename, 'r') as f:
            for line in f:
                if self.triple_count >= self.start_line:
                    batch += line
                    if line_count >= self.batch_size:
                        line_count = 1
                        self._send_to_db(batch)
                    else:
                        line_count += 1
                self.triple_count += 1
        # send the remaining items to the database
        if len(batch) > 0:
            self._send_to_db(batch)
                    
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

                 
        
        
        
        

class MissingKwargs(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return "Missing Kwargs -> %s" % repr(self.value)