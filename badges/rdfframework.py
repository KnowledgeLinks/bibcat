from flask import current_app, json
from .utilities import render_without_request
import requests
#from rdflib import RDF, RDFS, OWL, XSD, FOAF, SKOS, DOAP, DC, DCTERMS, VOID

class rdf_framework:
    '''base class for Knowledge Links' Graph database RDF vocabulary framework'''
    
    rdf_class_dict = {}        #stores the Triplestore defined class defintions
    class_initialized = False  #used to state if the the class was properly initialized with RDF definitions
    rdf_form_dict = {}
    forms_initialized = False
    
    def __init__(self):
        self.__generateClasses()
        self.__generateForms()
        
    def saveForm(self,Form):
        '''*** to be written ***
         recieves RDF_formfactory form, validates and saves the data'''
         
    
    def __generateClasses(self):
        if (self.class_initialized != True):
            classJson = self.__load_rdf_class_defintions()
            self.rdf_class_dict =  classJson
            self.class_initialized = True 
            for c in self.rdf_class_dict:
                setattr(self,c,rdf_class(classJson[c],c))  
    
    def __generateForms(self):
        if (self.forms_initialized != True):
            formJson = self.__load_rdf_form_defintions()
            self.rdf_form_dict =  formJson
            self.form_initialized = True 
            '''for c in self.rdf_class_dict:
                setattr(self,c,rdf_class(classJson[c],c)) '''
    
    def __load_rdf_class_defintions(self):
        '''Queries the triplestore for list of classes used in the app as defined in the kl_app.ttl file'''
        sparql = render_without_request(
            "jsonRDFclassDefinitions.rq",
            graph= "<http://knowledgelinks.io/ns/application-framework/>") #current_app.config.get('RDF_DEFINITION_GRAPH')) 
        formList =  requests.post( 
            current_app.config.get('TRIPLESTORE_URL'),
            data={"query": sparql,
                  "format": "json"})
        print("***** Querying tipplestore ****")
        return json.loads(formList.json().get('results').get('bindings')[0]['appClasses']['value'])
        
    def __load_rdf_form_defintions(self):
        '''Queries the triplestore for list of forms used in the app as defined in the kl_app.ttl file'''
        sparql = render_without_request(
            "jsonFormQueryTemplate.rq",
            graph= "<http://knowledgelinks.io/ns/application-framework/>") #current_app.config.get('RDF_DEFINITION_GRAPH')) 
        classList =  requests.post( 
            current_app.config.get('TRIPLESTORE_URL'),
            data={"query": sparql,
                  "format": "json"})
        print("***** Querying tipplestore for Forms ****")
        return json.loads(classList.json().get('results').get('bindings')[0]['appForms']['value'])
        
    def getProp(self,value):
        return "searching for prop"
        
        
class rdf_class:
    '''RDF Class for a an RDF Class object. 
       Uesed for manipulating and validating an RDF Class subject'''
       
    def __init__(self,jsonObj,className):
        for p in jsonObj:
            setattr(self,p,jsonObj[p])
        setattr(self,"className",className)
        #setattr(self,'reqProps',self.listRequired())
        #setattr(self,'dependantProps',self.listDependant())
    
    def save(self, data):
        '''validates and saves passed data for the class'''
        print("save",self.className)
        validRequiredProps = self.__validateRequiredProperties(data)
        validDependancies = self.__validateDependantProperties(data)
        print(json.dumps(validRequiredProps,indent=2))
        print(json.dumps(validDependancies,indent=2))
        
    def newUri(self):
        '''*** to be written ***
        generates a new URI 
          -- for fedora generates the container and returns the URI
          -- for blazegraph process will need to be created'''
        print("generating new URI")
        
    def validatePrimaryKey(self, dataValue):
        '''query to see if PrimaryKey is Valid'''
        returnVal = False
        try:
            pkey = self.primaryKey
            dataType = self.properties[self.findPropName(pkey)]['storageType']
            if dataType == 'literal':
                dataType = self.properties[self.findPropName(pkey)].get('range',dataType)
            return self.__makeTriple("?uri","a",iri(self.classUri)) + self.__makeTriple("?uri",iri(pkey),rdf_datatype(dataType).sparql(dataValue))
        except:
            pass
        else:
            return "no primaryKey"
            
    def listRequired(self):
        '''Returns a dictionary of the required properties for the class'''
        requiredList = set()
        for p in self.properties:
            if self.properties[p].get('requiredByDomain') == self.classUri:
                requiredList.add(p)
        if type(self.primaryKey) == "list":
            for key in self.primaryKey:
                requiredList.add(self.findPropName(key))
        else:
            requiredList.add(self.findPropName(self.primaryKey))
        return requiredList
                
    def listProperties(self):
        '''Returns a dictionary of the properties used for the class'''
        propertyList = set()
        for p in self.properties:
            propertyList.add(p)
        return propertyList 
            
    def listDependant(self):
        '''Returns a dictionary of properties that are depandant upon the creation of another object'''
        depandantList = set()
        for p in self.properties:
            rangeList = self.properties[p].get('range')
            for r in rangeList: 
                if r.get('storageType') == "object": # or self.properties[p].get('storageType') == "blanknode":
                    depandantList.add(p)
        return depandantList
        
    def __makeTriple (self,s,p,o):
        "takes a subject predicate and object and joins them with a space in between"
        return s + " " + p + " " + o + " . "
        
    def findPropName (self,propUri):
        "cycle through the class properties object to find the property name"
        #print(self.properties)
        for p in self.properties:
            #print("p--",p," -- ",self.properties[p]['propUri'])
            if self.properties[p]['propUri'] == propUri:
               # print ('propName is ',p)
                return p
                
    def formatDataType(self,dataValue,dataType):
        "formats a dataValue and dataType for SPARQL query"
        if dataType == "literal":
            return '"' + dataValue + '"'
        elif dataType == "object":
            return self.iri(dataValue)
        else:
            return dataValue
            
    def __validateRequiredProperties (self,data):
        '''Validates whether all required properties have been supplied and contain data '''
        returnError = []
        #create sets for evaluating requiredFields
        req = self.listRequired()
        dataProps = set()
        for p in data:
            #remove empty data properties from consideration
            if IsNotNull(data[p]):
                dataProps.add(p)
        #Test to see if all the required fields are supplied    
        missingRequiredProperties = req - dataProps
        if len(missingRequiredProperties)>0:
            missingUris = []
            for m in missingRequiredProperties:
                missingUris.append(self.properties[m]['propUri'])
            returnError.append({"errorType":"missingRequiredProperties","errorData":{"class":self.classUri,"properties":missingUris}})
        if len(returnError)>0:
            return returnError
        else:
            return ["valid"]
            
    def __validateDependantProperties (self,data):
        '''Validates that all supplied dependant properties have a uri as an object'''
        dep = self.listDependant()
        returnError = []
        dataProps = set()
        for p in data:
            #remove empty data properties from consideration
            if IsNotNull(data[p]):
                dataProps.add(p)
        for p in dep:
            dataValue = data.get(p)
            if (IsNotNull(dataValue)):
                propDetails = self.properties[p]
                r = propDetails.get('range')
                literalOk = false
                for i in r:
                    if i.get('storageType')=='literal':
                        literalOk = True
                if not IsValidObject(dataValue) and not literalOk:
                    returnError.append({"errorType":"missingDependantObject","errorData":{"class":self.classUri,"properties":propDetails.get('propUri')}})
        if len(returnError)>0:
            return returnError
        else:
            return ["valid"]       
        
    
class rdf_datatype:
    "This class will generate a rdf data type"
    def __init__(self, rdfDataType):
        self.__dataTypes(rdfDataType)
        
    def sparql(self,dataValue):
        "formats a value for a sparql triple"
        if self.name == "object":
            return iri(dataValue)
        elif self.name == "literal":
            return '"' + dataValue + '"'
        elif self.name == "boolean":
            return '"' + str(dataValue).lower() + '"^^' + self.prefix
        else:
            return '"' + dataValue + '"^^' + self.prefix
        
    def __dataTypes(self,lookup):
        "sets the class attributes"
        val = lookup.replace("http://www.w3.org/2001/XMLSchema#","").replace("xsd:","").replace("rdf:","").replace("http://www.w3.org/1999/02/22-rdf-syntax-ns#","")
        self.prefix = "xsd:" + val
        self.iri = iri("http://www.w3.org/2001/XMLSchema#" + val)
        self.name = val
        if val.lower() == "literal" or val.lower() == "langstring":
            self.prefix = "rdf:" + val
            self.iri = iri("http://www.w3.org/1999/02/22-rdf-syntax-ns#" + val)
        elif val.lower() == "object":
            self.prefix = "objInject"
            self.uri = "objInject"
        
        
def iri(uriString):
        "converts a string to an IRI or returns an IRI if already formated"
        if uriString[:1] != "<":
            uriString = "<" + uriString.strip()
        if uriString[len(uriString)-1:] != ">":
            uriString = uriString.strip() + ">"
        return uriString

def IsNotNull(value):
    return value is not None and len(value) > 0
    
def IsValidObject(uriString):
    '''Test to see if the string is a object store'''
    return True
    
def AssertionImageBakingProccessor():
    '''Application sends badge image to the a badge baking service with the assertion.'''
    return "not developed"
    
def CSVstringToMultiPropertyProccessor(data, propUri, subjectUri, g):
    '''Application takes a CSV string and adds each value as a seperate triple to the class instance.'''
    vals = data.split(',')
    returnTriple = IRI(subjectUri)
    for v in vals:
        returnTriple += "\n " + IRI(propUri) + ""
    return ""
    
def EmailVerificationProccessor():
    '''Application application initiates a proccess to verify the email address is a valid working address.'''
    return "not developed"
    
def PasswordProccessor():
    '''Application should proccess as a password for storage. i.e. salting and hashing'''
    return "not developed"
    
def SaltProccessor():
    '''Application should generate a random Salt value to store.'''
    return "not developed"
    
def CalculationProccessor(data):
    '''Application should proccess the property according to the rules listed int he kds:calulation property.'''
    return "not developed"
    