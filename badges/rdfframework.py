from flask import current_app, json
from .utilities import render_without_request
import requests
from rdflib import Namespace, RDF, RDFS, OWL, XSD #! Not sure what VOID is

try:
    from flask_wtf import Form
    from flask_wtf.file import FileField
except ImportError:
    from wtforms import Form
    from wtforms.fields import FieldField
from wtforms.fields import StringField, TextAreaField, PasswordField, BooleanField, FileField, DateField, DateTimeField, SelectField, Field
from wtforms.validators import Length, URL, Email, EqualTo, NumberRange, Required, Regexp, InputRequired 
import wtforms.form
from wtforms.widgets import TextInput

DC = Namespace("http://purl.org/dc/elements/1.1/")
DCTERMS = Namespace("http://purl.org/dc/terms/") 
DOAP = Namespace("http://usefulinc.com/ns/doap#")
FOAF = Namespace("http://xmlns.com/foaf/spec/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

class RDFFramework(object):
    '''base class for Knowledge Links' Graph database RDF vocabulary framework'''
    
    rdf_class_dict = {}        #stores the Triplestore defined class defintions
    class_initialized = False  #used to state if the the class was properly initialized with RDF definitions
    rdf_form_dict = {}
    forms_initialized = False
    rdf_app_dict = {}
    app_initialized = False
    
    def __init__(self):
        self.__loadApp()
        self.__generateClasses()
        self.__generateForms()
        
    def saveForm(self,Form):
        '''*** to be written ***
         recieves RDF_formfactory form, validates and saves the data'''
        pass
         
    
    def __loadApp(self):
        if (self.app_initialized != True):
            appJson = self.__load_application_defaults()
            self.rdf_app_dict =  appJson
            self.app_initialized = True      
    
    def __generateClasses(self):
        if (rdf_framework.class_initialized != True):
            classJson = self.__load_rdf_class_defintions()
            self.rdf_class_dict =  classJson
            rdf_framework.class_initialized = True 
            for c in self.rdf_class_dict:
                setattr(self,c,rdf_class(classJson[c],c))  
    
    def __generateForms(self):
        if (self.forms_initialized != True):
            formJson = self.__load_rdf_form_defintions()
            self.rdf_form_dict =  formJson
            self.form_initialized = True 
            '''for c in self.rdf_class_dict:
                setattr(self,c,rdf_class(classJson[c],c)) '''
    
    def __load_application_defaults(self):
        '''Queries the triplestore for settings defined for the application in the kl_app.ttl file'''
        sparql = render_without_request(
            "jsonApplicationDefaults.rq",
            graph= "<http://knowledgelinks.io/ns/application-framework/>") #current_app.config.get('RDF_DEFINITION_GRAPH')) 
        formList =  requests.post( 
            current_app.config.get('TRIPLESTORE_URL'),
            data={"query": sparql,
                  "format": "json"})
        print("***** Querying tipplestore ****")
        return json.loads(formList.json().get('results').get('bindings')[0]['app']['value'])
        
    def __load_rdf_class_defintions(self):
        '''Queries the triplestore for list of classes used in the app as defined in the kl_app.ttl file'''
        sparql = render_without_request(
            "jsonRDFclassDefinitions.rq",
            graph= "<http://knowledgelinks.io/ns/application-framework/>") #current_app.config.get('RDF_DEFINITION_GRAPH')) 
        formList =  requests.post( 
            current_app.config.get('TRIPLESTORE_URL'),
            data={"query": sparql,
                  "format": "json"})
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
        
        
class RDFClass(object):
    '''RDF Class for an RDF Class object. 
       Used for manipulating and validating an RDF Class subject'''
       
    def __init__(self, jsonObj, className):
        for p in jsonObj:
            setattr(self, p, jsonObj[p])
        setattr(self, "className", className)
    
    def save(self, data):
        '''validates and saves passed data for the class'''
        if not data:
            raise ValueError("Save requires data dictionary")
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
        "takes a subject predicate and object and joins them with a sp ace in between"
        return "{s} {p} {o} .".format(s=s, p=p, o=0)

    def validateRequiredProperties(self, data):
        '''Validates whether all required properties have been supplied and contain data '''
        returnError = []
        #create sets for evaluating requiredFields
        required = self.listRequired()
        dataProps = set()
        for p in data:
            #remove empty data properties from consideration
            if IsNotNull(data[p]):
                dataProps.add(p)
        #Test to see if all the required fields are supplied    
        missingRequiredProperties = required - dataProps
        if len(missingRequiredProperties)>0:
            missingUris = []
            for m in missingRequiredProperties:
                missingUris.append(self.properties[m]['propUri'])
            returnError.append({
                "errorType":"missingRequiredProperties",
                "errorData":{
                    "class":self.classUri,
                    "properties":missingUris}})
        if len(returnError)>0:
            return returnError
        else:
            return ["valid"]
            
    def validateDependantProperties(self, data):
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
                    returnError.append({
                        "errorType":"missingDependantObject",
                        "errorData":{
                            "class":self.classUri,
                            "properties":propDetails.get('propUri')}})
        if len(returnError)>0:
            return returnError
        else:
            return ["valid"]       


    def findPropName (self,propUri):
        "cycle through the class properties object to find the property name"
        #print(self.properties)
        for p in self.properties:
            #print("p--",p," -- ",self.properties[p]['propUri'])
            if self.properties[p]['propUri'] == propUri:
                return p
                
    def formatDataType(self,dataValue,dataType):
        "formats a dataValue and dataType for SPARQL query"
        if dataType == "literal":
            return '"{}"'.format(dataValue)
        elif dataType == "object":
            return self.iri(dataValue)
        else:
            return dataValue


class RDFDataType(object):
    "This class will generate a rdf data type"

    def __init__(self, rdfDataType):
        self.lookup = rdfDataType
        #! What happens if none of these replacements? 
        val = self.lookup.replace(str(XSD),"").\
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
    
                
        
#! Should we test to see if uriString is a valid IRI?
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
    
def getWtFormField(field):
    form_field = None
    fieldLabel = field.get("formLabelName",'')
    #print("______label:", fieldLabel)
    fieldName = field.get("formFieldName",'')
    fieldTypeObj = field.get("fieldType",{})
    fieldValidators = getWtValidators(field)
    fieldType = "kdr:" + fieldTypeObj.get('type','').replace("http://knowledgelinks.io/ns/data-resources/","")
    #print("fieldType: ",fieldType)
    if fieldType == 'kdr:TextField':
        form_field = StringField(fieldLabel, fieldValidators)
    elif fieldType == 'kdr:ServerField':
        form_field = None
        #form_field = StringField(fieldLabel, fieldValidators)
    elif fieldType == 'kdr:TextAreaField':
        form_field = TextAreaField(fieldLabel, fieldValidators)
    elif fieldType == 'kdr:PasswordField':
        #print("!!!! Mode: ",fieldTypeObj.get('fieldMode'))
        #print(field)
        if fieldTypeObj.get('fieldMode') == "InitialPassword":   
            form_field = [
                            {"fieldName":fieldName,"field":PasswordField(fieldLabel, fieldValidators)},
                            {"fieldName":fieldName + "_confirm", "field":PasswordField("Re-enter")}
                         ]
        elif fieldTypeObj.get('fieldMode') == "ChangePassword":
            form_field = [
                            {"fieldName":fieldName + "_old","field":PasswordField("Current")},
                            {"fieldName":fieldName + "_new","field":PasswordField("New")},
                            {"fieldName":fieldName + "_confirm", "field":PasswordField("Re-enter")}
                         ]
        elif fieldTypeObj.get('fieldMode') == "LoginPassword":
            form_field = PasswordField(fieldLabel, fieldValidators)
    elif fieldType == 'kdr:BooleanField':
        form_field = BooleanField(fieldLabel, fieldValidators)
    elif fieldType == 'kdr:FileField':
        form_field = FileField(fieldLabel, fieldValidators)
    elif fieldType == 'kdr:DateField':
        form_field = DateField(fieldLabel, fieldValidators)
    elif fieldType == 'kdr:DateTimeField':
        form_field = DateTimeField(fieldLabel, fieldValidators)
    elif fieldType == 'kdr:SelectField':
        #print("--Select Field: ",fieldLabel, fieldValidators)
        form_field = SelectField(fieldLabel, fieldValidators)
        #form_field = StringField(fieldLabel, fieldValidators)
    elif fieldType == 'kdr:ImageFileOrURLField':
        form_field = [
                        {"fieldName":fieldName +"_image", "field":FileField("Image File")},
                        {"fieldName":fieldName + "_url", "field":StringField("Image Url",[URL])}
                     ]
    else:
        form_field = StringField(fieldLabel, fieldValidators)
    #print("--form_field: ",form_field)
    return form_field 

def getWtValidators(field):
    '''reads the list of validators for the field and returns the wtforms validator list'''
    fieldValidators = []
    if field.get('required') == True:
        fieldValidators.append(InputRequired())
    
    validatorList = makeList(field.get('validators', []))
    for v in validatorList:
        vType = v['type'].replace("http://knowledgelinks.io/ns/data-resources/","kdr:")
        if vType == 'kdr:PasswordValidator':
            fieldValidators.append(EqualTo(fieldName +'_confirm', message='Passwords must match'))
        if vType == 'kdr:EmailValidator':
            fieldValidators.append(Email(message='Enter a valid email address'))
        if vType ==  'kdr:UrlValidator':
            fieldValidators.append(URL(message='Enter a valid URL/web address'))
        if vType ==  'kdr:UniqueValueValidator':
            fieldValidators.append(UniqueDatabaseCheck(message='The Value enter is already exists'))
        if vType ==  'kdr:StringLengthValidator':
            p = v.get('parameters')
            p1 = p.split(',')
            pObj={}
            for param in p1:
                nParam = param.split('=')
                pObj[nParam[0]]=nParam[1]
            fieldValidators.append(Length(min=pObj.get('min'),max=pObj.get('max')))
    return fieldValidators
      
def getFieldJson (field,instructions,instance,userInfo,itemPermissions=[]):
    '''This function will read through the RDF defined info and proccess the json to retrun the correct values for the instance, security and details'''
    
    rdfApp = get_framework().rdf_app_dict['application']
   
    # Determine Security Access
    nField={}
    accessLevel = getFieldSecurityAccess(field,userInfo,itemPermissions)
    if "Read" not in accessLevel:
        return None
    nField['accessLevel'] = accessLevel

    # get form instance info 
    formInstanceInfo = {}
    formFieldInstanceTypeList = makeList(field.get('formInstance',field.get('formDefault',{}).get('formInstance',[])))
    for f in formFieldInstanceTypeList:
        if f.get('formInstanceType') == instance:
            formInstanceInfo = f

    # Determine the field paramaters
    nField['formFieldName'] = formInstanceInfo.get('formFieldName',field.get("formFieldName",field.get('formDefault',{}).get('formFieldName',"")))
    
    nField['fieldType'] = formInstanceInfo.get('fieldType',field.get('fieldType',field.get('formDefault',{}).get('fieldType',"")))
    #print("fieldType Type: ",nField['formFieldName']," - ",nField['fieldType'])
    if not isinstance(nField['fieldType'],dict):
        nField['fieldType'] = {"type":nField['fieldType']}
    
    nField['formLabelName'] = formInstanceInfo.get('formlabelName',field.get("formLabelName",field.get('formDefault',{}).get('formLabelName',"")))
    nField['formFieldHelp'] = formInstanceInfo.get('formFieldHelp',field.get("formFieldHelp",field.get('formDefault',{}).get('formFieldHelp',"")))
    nField['formFieldOrder'] = formInstanceInfo.get('formFieldOrder',field.get("formFieldOrder",field.get('formDefault',{}).get('formFieldOrder',"")))
    nField['formLayoutRow'] = formInstanceInfo.get('formLayoutRow',field.get("formLayoutRow",field.get('formDefault',{}).get('formLayoutRow',"")))
    
    # get applicationActionList 
    nField['actionList'] = makeSet(formInstanceInfo.get('applicationAction',set()))
    nField['actionList'].union(makeSet(field.get('applicationAction',set())))
    nField['actionList'] = list(nField['actionList'])
    # get valiator list
    nField['validators'] = makeList(formInstanceInfo.get('formValidation',[]))
    nField['validators'] += makeList(field.get('formValidation',[]))
    nField['validators'] += makeList(field.get('propertyValidation',[]))    
    
    # get proccessing list
    nField['proccessors'] = makeList(formInstanceInfo.get('formProccessing',[]))
    nField['proccessors'] += makeList(field.get('formProccessing',[]))
    nField['proccessors'] += makeList(field.get('propertyProccessing',[]))
        
    # get required state
    required = False
    if (field.get('propName') in makeList(field.get('classInfo',{}).get('primaryKey',[]))) or (field.get('requiredField',False)) :
        required = True
    nField['required'] = required
    
    # Determine EditState
    if ("Write" in accessLevel) and ("http://knowledgelinks.io/ns/data-resources/NotEditable" not in nField['actionList']):
        nField['editable'] = True
    else:
        nField['editable'] = False
        
    # Determine css classes
    css = formInstanceInfo.get('overideCss',field.get('overideCss',instructions.get('overideCss',None)))
    if css is None:
        css = rdfApp.get('formDefault',{}).get('fieldCss','')
        css = css.strip() + " " + instructions.get('propertyAddOnCss','')
        css = css.strip() + " " + formInstanceInfo.get('addOnCss',field.get('addOnCss',''))
        css = css.strip()
    nField['css'] = css
    
    return nField

def getFormInstructionJson (instructions,instance):
    '''This function will read through the RDF defined info and proccess the json to retrun the correct values the instance of the form an instructions'''
    
    rdfApp = get_framework().rdf_app_dict['application']
    print("inst------",instructions) 
# get form instance info 
    formInstanceInfo = {}
    formInstanceTypeList = makeList(instructions.get('formInstance',[]))
    for f in formInstanceTypeList:
        if f.get('formInstanceType') == instance:
            formInstanceInfo = f
    nInstr = {}
    print("------",formInstanceInfo)    
#Determine the form paramaters
    nInstr['formTitle'] = formInstanceInfo.get('formTitle',instructions.get("formTitle",""))
    nInstr['formDescription'] = formInstanceInfo.get('formDescription',instructions.get("formDescription",""))
    nInstr['form_Method'] = formInstanceInfo.get('form_Method',instructions.get("form_Method",""))
    nInstr['form_enctype'] = formInstanceInfo.get('form_enctype',instructions.get("form_enctype",""))
    nInstr['propertyAddOnCss'] = formInstanceInfo.get('propertyAddOnCss',instructions.get("propertyAddOnCss",""))
        
# Determine css classes
    #form row css
    css = formInstanceInfo.get('rowOverideCss',instructions.get('rowOverideCss',None))
    if css is None:
        css = rdfApp.get('formDefault',{}).get('rowCss','')
        css = css.strip() + " " + formInstanceInfo.get('rowAddOnCss',instructions.get('rowAddOnCss',''))
        css = css.strip() 
        css.strip()
    nInstr['rowCss'] = css
    
    #form general css
    css = formInstanceInfo.get('formOverideCss',instructions.get('formOverideCss',None))
    if css is None:
        css = rdfApp.get('formDefault',{}).get('formCss','')
        css = css.strip() + " " + formInstanceInfo.get('formAddOnCss',instructions.get('formAddOnCss',''))
        css = css.strip() 
        css.strip()
    nInstr['formCss'] = css
    
    return nInstr
    
def getFieldSecurityAccess(field,userInfo,itemPermissions=[]): 
    '''This function will return level security access allowed for the field'''
    #Check application wide access
    appSecurity = userInfo.get('applicationSecurity',set())
    #Check class access
    classAccessList = makeList(field.get('classInfo',{"classSecurity":[]}).get("classSecurity",[]))
    classAccess = set()
    if len(classAccessList) > 0:
        for i in classAccessList:
            if (i['agent'] in userInfo['userGroups']):
                classAccess.add(i.get('mode'))
    
    #check property security
    propertyAccessList = makeList(field.get('propertySecurity',[]))
    propertyAccess = set()
    if len(propertyAccessList) > 0:
        for i in propertyAccessList:
            if (i['agent'] in userInfo['userGroups']):
                classAccess.add(i.get('mode'))           
            
    #check item permissions 
    itemAccessList = makeList(field.get('itemSecurity',[]))
    itemAccess = set()
    if len(itemAccessList) > 0:
        for i in itemAccessList:
            if (i['agent'] in userInfo['userGroups']):
                classAccess.add(i.get('mode'))
    
    mainAccess = itemAccess.intersection(propertyAccess)
    if "SuperUser" in appSecurity:
        return set('Read','Write')            
    elif len(mainAccess)>0:
        return mainAccess   
    elif len(classAccess)>0:
        return classAccess
    elif len(appSecurity)>0:
        return appSecurity
    else:
        return set()
        
               
def rdf_framework_form_factory(name,instance):
    rdf_form = type(name, (Form, ), {})
    appForm = get_framework().rdf_form_dict.get(name,{})
    fields = appForm.get('properties')
    instructions = getFormInstructionJson(appForm.get('formInstructions'),instance)
    print('instructions: \n',json.dumps(instructions,indent=4))
    # get the number of rows in the form and define the fieldList as a mulit-demensional list
    fieldList = []
    formRows = fields[len(fields)-1].get('formLayoutRow',1)
    for i in range(0,formRows):
        fieldList.append([])
        
    '''************************** Testing Variable *******************************'''
    userInfo = {
        "userGroups":["http://knowledgelinks.io/ns/data-resources/SysAdmin-SG"],
        'applicationSecurity':["Read","Write"]
    }
    '''**************************************************************************'''
    for f in fields:
        field = getFieldJson (f,instructions,instance,userInfo)
        if field:
            formRow = field.get('formLayoutRow',1)-1
            form_field = getWtFormField(field)
            if isinstance(form_field, list):
                i=0
                #print("____----")
                for fld in form_field:
                    #print(fld)
                    if fld.get('field'):
                        nField = field
                        nField['formFieldName'] = fld['fieldName']
                        nField['formFieldOrder'] = nField['formFieldOrder'] + i
                        
                        fieldList[formRow].append(dict.copy(nField))
                        #print("--Nfield: ",nField)
                        setattr(rdf_form, fld['fieldName'], fld['field'])
                        i += .1
            else:
                #print(field['formFieldName']," - ",form_field)
                if form_field:
                    #print("set --- ",field)
                    fieldList[formRow].append(field)
                    setattr(rdf_form, field['formFieldName'], form_field)
    return {"formInfo":appForm, "instructions":instructions, "fieldList": fieldList, "instance":instance, "form":rdf_form}
    #return rdf_form
    
def makeList(value):
    if not isinstance(value, list):
        value = [value]
    return value
    
def makeSet(value):
    returnSet = set()
    if isinstance(value, list):
        for i in value:
            returnSet.add(i)
    elif isinstance(value, set):
        returnSet = value
    else:
        returnSet.add(value)
    return returnSet
    
def get_framework():
    global rdf
    try:
        test = rdf
    except:
        rdf = rdf_framework()
    return rdf
    
def querySelectOptions(field):
    prefix = '''
        prefix acl: <http://www.w3.org/ns/auth/acl#> 
        prefix foaf: <http://xmlns.com/foaf/0.1/> 
        prefix kds: <http://knowledgelinks.io/ns/data-structures/> 
        prefix kdr: <http://knowledgelinks.io/ns/data-resources/> 
        prefix obi: <https://w3id.org/openbadges#> 
        prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
        prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> 
        prefix schema: <https://schema.org/> 
        prefix xsd: <http://www.w3.org/2001/XMLSchema#>
    '''
    selectQuery = field.get('fieldType',{}).get('selectQuery',None)
    selectList = {}
    options = []
    if selectQuery:
        selectList =  requests.post( 
            current_app.config.get('TRIPLESTORE_URL'),
            data={"query": prefix + selectQuery,
                  "format": "json"})
        rawOptions = selectList.json().get('results',{}).get('bindings',[])
        boundVar = field.get('fieldType',{}).get('selectBoundValue','').replace("?","")
        displayVar = field.get('fieldType',{}).get('selectDisplay','').replace("?","")
        for row in rawOptions:
            options.append(
                {
                    "id":row.get(boundVar,{}).get('value',''),
                    "value":row.get(displayVar,{}).get('value','')
                })
    return options
    
def loadFormSelectOptions(rdfForm,fldList):
    for row in fldList:
        for fld in row:
            if fld.get('fieldType',{}).get('type',"") == 'http://knowledgelinks.io/ns/data-resources/SelectField':
                options = querySelectOptions(fld)
                print("oooooooo\n",options)
                fldName = fld.get('formFieldName',None)
                getattr(rdfForm,fldName).choices = [(o['id'], o['value']) for o in options]
    return rdfForm
