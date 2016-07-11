""" This provides classes for reading a large turtle file. This is not
indented to replace RDF or use of a triplestore. Some large reference data sets
may want to be read an pushed directly into another database with out having to 
through the the triplestore. 
"""

__author__ = "Jeremy Nelson, Mike Stabile"

import os
import logging
import inspect
import rdflib

MODULE_NAME = os.path.basename(inspect.stack()[0][1])

class LargeTurtleReader (object):
    """ Reads a large turtle file and provides options for returning the data
    as specified 
    
    Args:
        filepath: the name of the turtle file.
        batch_size: the number of triples to return in each set.
    """
    # set the classname
    ln = "%s.LargeTurtleReader" % MODULE_NAME
    # set specific logging handler for the module allows turning on and off
    # debug as required
    log_level = logging.DEBUG
    
    def __init__(self, filepath, batch_size, sparql_filter, **kwargs):
        # setup logger
        lg = logging.getLogger("%s-%s" % (self.ln, inspect.stack()[0][3]))
        lg.setLevel(self.log_level)
        
        self.filepath = filepath
        self.batch_size = batch_size
        self.sparql_filter = sparql_filter
        self.open_file = None
        self.file_encoding = kwargs.get("file_encoding","utf-8")
        #self._scan_linepos()
        self._read_prefix()
        lg.debug("\nfilepath: %s\nbatch_size: %s\nsparql_filter:\n%s\nprefix:\n%s\nrdfstart: %s", 
                 filepath,
                 batch_size,
                 sparql_filter,
                 self.prefix,
                 self.rdfstart)
        
    def get_batch(self):
        """ reads and returns the next batch
        
        args:
            None
        
        returns:
            batch: the set triples
        """
        # setup logger
        lg = logging.getLogger("%s-%s" % (self.ln, inspect.stack()[0][3]))
        lg.setLevel(self.log_level)
        
        with open(self.filepath, encoding=self.file_encoding) as inf:
            for line in inf:
            
            
    def _read_prefix(self):
        """ Reads the the beginning of a turtle file and sets the prefix's used
        in that file and sets the prefix attribute """
        rdfstart = 0
        prefixes = []
        with open(self.filepath, encoding=self.file_encoding) as inf:
            for line in inf:
                current_line = str(line).strip()
                if current_line.startswith("@prefix"):
                    prefixes.append(current_line.replace("\n",""))
                    rdfstart += len(line)
                elif len(current_line) > 10:
                    break
                else:
                    rdfstart += len(line)
        self.rdfstart = rdfstart
        self.prefix = "\n".join(prefixes)
        self._start = self.rdfstart
                
    def _scan_linepos(self):
        """sets the seek offsets of the beginning of each line. This will 
        allow for open and closing the file at appropriate locations"""
        
        linepos = []
        offset = 0
        with open(self.filepath, encoding=self.file_encoding) as inf:     
            for line in inf:
                linepos.append(offset)
                offset += len(line)
        self.line_positions = linepos
    
    def __iter__(self):
        return self

    def __next__(self):
        batch = self.get_batch():
        return batch
        
        