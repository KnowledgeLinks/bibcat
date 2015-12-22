from flask import current_app, json
from .utilities import render_without_request
import requests
from rdflib import Namespace, RDF, RDFS, OWL, XSD #! Not sure what VOID is

DC = Namespace("http://purl.org/dc/elements/1.1/")
DCTERMS = Namespace("http://purl.org/dc/terms/") 
DOAP = Namespace("http://usefulinc.com/ns/doap#")
FOAF = Namespace("http://xmlns.com/foaf/spec/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

class rdf_framework(object):
    '''base class for Knowledge Links' Graph database RDF vocabulary framework'''
    
    rdf_class_dict = {}        #stores the Triplestore defined class defintions
    class_initialized = False  #used to state if the the class was properly initialized with RDF definitions
    
    def __init__(self):
        self.__generateClasses()
        
    def saveForm(self,Form):
        '''*** to be written ***
         recieves RDF_formfactory form, validates and saves the data'''
        pass
         
    
    def __generateClasses(self):
        if (rdf_framework.class_initialized != True):
            classJson = self.__load_rdf_class_defintions()
            self.rdf_class_dict =  classJson
            rdf_framework.class_initialized = True 
            for c in self.rdf_class_dict:
                setattr(self,c,rdf_class(classJson[c]))  
    
    def __load_rdf_class_defintions(self):
        '''Queries the triplestore for list of classes used in the app as defined in the kl_app.ttl file'''
        sparql = render_without_request(
            "jsonRDFclassDefinitions.rq",
            graph= "klob:extensions") #current_app.config.get('RDF_DEFINITION_GRAPH')) 
        classList =  requests.post( 
            current_app.config.get('TRIPLESTORE_URL'),
            data={"query": sparql,
                  "format": "json"})
        return json.loads(classList.json().get('results').get('bindings')[0]['appClasses']['value'])

#! Standard Python practice is to use CamelCase for Class names
#! so rdf_class could be RDFClass, RdfClass, or rdfClass
class rdf_class(object):
    '''RDF Class for a RDF Class object. 
       Used for manipulating and validating an RDF Class subject'''
       
    def __init__(self,jsonObj):
        for p in jsonObj:
            setattr(self, p, jsonObj[p])
    
    def save(self, data):
        '''validates and saves passed data for the class'''
        print("save",self.className)
        
    def newUri(self):
        '''*** to be written ***
        generates a new URI 
          -- for fedora generates the container and returns the URI
          -- for blazegraph process will need to be created'''
        print("generating new URI")
        
    def validatePrimaryKey(self, dataValue):
        '''query to see if PrimaryKey is Valid'''
        returnVal = False #! This variable is never used
        try:
            pkey = self.primaryKey
            dataType = self.properties[self.findPropName(pkey)]['storageType']
            if dataType == 'literal':
                dataType = self.properties[self.findPropName(pkey)].get('range',dataType)
            return self.__makeTriple(
                    "?uri",
                     "a",
                     iri(self.classUri)) + self.__makeTriple("?uri", iri(pkey), rdf_datatype(dataType).sparql(dataValue))
        except:
            pass
        else:
            return "no primaryKey"
        
    def __makeTriple (self,s,p,o):
        "takes a subject predicate and object and joins them with a sp ace in between"
        return "{s} {p} {o} .".format(s=s, p=p, o=0)
        
    def findPropName (self,propUri):
        "cycle through the class properties object to find the property name"
        #print(self.properties)
        for p in self.properties:
            #print("p--",p," -- ",self.properties[p]['propUri'])
            if self.properties[p]['propUri'] == propUri:
                #print ('propName is ',p)
                return p
                
    def formatDataType(self,dataValue,dataType):
        "formats a dataValue and dataType for SPARQL query"
        if dataType == "literal":
            return '"{}"'.format(dataValue)
        elif dataType == "object":
            return self.iri(dataValue)
        else:
            return dataValue

#! Standard Python practice is to use CamelCase for Class names
#! so rdf_datatype could be RDFDataType, RdfDataType, or rdfDataType
class rdf_datatype(object):
    "This class will generate a rdf data type"

    def __init__(self, rdfDataType):
        self.__dataTypes__(rdfDataType)

    def sparql(self,dataValue):
        "formats a value for a sparql triple"
        if self.name == "object":
            return iri(dataValue)
        elif self.name == "literal":
            return '"{}"'.format(dataValue)
        elif self.name == "boolean":
            return '"{}"^^{}'.format(str(dataValue).lower(),
                                      self.prefix)
        else:
            return '"{}"^^{}'.format(dataValue, self.prefix)
    
    #! Why isn't this function in __init__, will it ever be used outside of
    #! __init__ call?   
    def __dataTypes__(self,lookup):
        "sets the class attributes"
        #! What happens if none of these replacements? 
        val = lookup.replace(str(XSD),"").\
                replace("xsd:","").\
                replace("rdf:","").\
                replace(str(RDF),"")
        self.prefix = "xsd:{}".format(val)
        self.iri = iri("{}{}".format(str(XSD), val))
        self.name = val
        if val.lower() == "literal" or val.lower() == "langstring":
            self.prefix = "rdf:{}".format(val)
            self.iri = iri(str(RDF) + val)
        elif val.lower() == "object":
            self.prefix = "objInject"
            #! Why is uri a new property if an object?
            self.uri = "objInject"
        
        
#! Should we test to see if uriString is a valid IRI?
def iri(uriString):
    "converts a string to an IRI or returns an IRI if already formated"
    if uriString[:1] != "<":
        uriString = "<" + uriString.strip()
    if uriString[len(uriString)-1:] != ">":
        uriString = uriString.strip() + ">"
    return uriString

