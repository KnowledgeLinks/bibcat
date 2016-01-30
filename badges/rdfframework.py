"""Module for RDF forms managment""" 
__author__ ="Mike Stabile, Jeremy Nelson"

import os
import requests
import random
import re
import time
import inspect 
from flask import current_app, json
from jinja2 import Template
from .utilities import render_without_request
from rdflib import Namespace, RDF, RDFS, OWL, XSD #! Not sure what VOID is
#need this for testing if form data is an instance of FileStorage
# MultiDict used for passing data to forms
from werkzeug.datastructures import FileStorage, MultiDict 
from passlib.hash import sha256_crypt
from dateutil.parser import *
from base64 import b64encode

#from datetime import *
 
try:
    from flask_wtf import Form
    from flask_wtf.file import FileField
except ImportError:
    from wtforms import Form
    from wtforms.fields import FieldField
from wtforms.fields import StringField, TextAreaField, PasswordField, \
        BooleanField, FileField, DateField, DateTimeField, SelectField, Field
from wtforms.validators import Length, URL, Email, EqualTo, NumberRange, \
        Required, Regexp, InputRequired 
import wtforms.form
#from wtforms_components import TimeField, read_only
from wtforms.widgets import TextInput

DC = Namespace("http://purl.org/dc/elements/1.1/")
DCTERMS = Namespace("http://purl.org/dc/terms/") 
DOAP = Namespace("http://usefulinc.com/ns/doap#")
FOAF = Namespace("http://xmlns.com/foaf/spec/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

class RdfFramework(object):
    ''' base class for Knowledge Links' Graph database RDF vocabulary 
        framework'''
    
    rdf_class_dict = {}       # stores the Triplestore defined class defintions
    class_initialized = False # used to state if the the class was properly 
                              #     initialized with RDF definitions
    rdf_form_dict = {}        # stores the Triplestore defined form definitions
    forms_initialized = False # used to state if the form definitions have 
                              #     been initialized
    rdf_app_dict = {}         # stors the the Triplestore definged application 
                              #     settings
    app_initialized = False   # states if the application has been initialized
    valueProcessors = []

    def __init__(self):
        self.__loadApp()
        self.__generateClasses()
        self.__generateForms()
           
    
    def getClassName(self, classUri):
        '''This method returns the rdf class name for the supplied Class URI'''
        for rdfClass in self.rdf_class_dict:
            currentClassUri = self.rdf_class_dict.get(rdfClass,{}).get(\
                    "classUri")
            if currentClassUri == classUri:
                return rdfClass
        return ''
        
    def getProperty(self, **kwargs):
        ''' Method returns a list of the property json objects where the 
            property is used
        
        keyword Args:
            className: *Optional the name of Class 
            classUri: *Optional the Uri of the Class
            propName: The Name of the property
            propUri: The URI of the property
            ** the PropName or URI is required'''
        returnList = []    
        className = kwargs.get("className")
        classUri = kwargs.get("classUri")
        propName = kwargs.get("propName")
        propUri = kwargs.get("propUri")
        if className or classUri:
            if classUri:
                className = self.getClassName(classUri)
            if propUri:
                returnList.append(getattr(self,className).getProperty(\
                        propUri=propUri))
            else:
                returnList.append(getattr(self,className).getProperty(\
                        propName=propName))
        else:
            for rdfClass in self.rdf_class_dict:
                if propName:
                    currentClassProp = getattr(self,rdfClass).getProperty(\
                            propName=propName)
                else:
                    currentClassProp = getattr(self,rdfClass).getProperty(\
                            propUri=propUri)
                if currentClassProp:
                    returnList.append(currentClassProp)
        return returnList      
    
    def formExists(self,form_name,form_instance):
        '''Tests to see if the form and instance is valid'''
        
        if not form_name in self.rdf_form_dict:
            return False
        instances = makeList(self.rdf_form_dict[form_name]['formInstructions'\
                ].get('formInstance',[]))
        for instance in instances:
            if "http://knowledgelinks.io/ns/data-resources/{}".format(\
                    form_instance) == instance.get('formInstanceType'):
                return True
        return False
    
    def getFormName(self,form_uri):
        '''returns the form name for a form
        
        rightnow this is a simple regex but is in place if a more
        complicated search method needs to be used in the future'''
        if form_uri:
            return re.sub(r"^(.*[#/])", "", form_uri)
        else:
            return None

    def saveForm(self, rdfForm):
        '''Recieves RDF_formfactory form, validates and saves the data
         
         *** Steps ***
         - group fields by class
         - validate the form data for class requirements
         - determine the class save order. classes with no dependant properties
           saved first
         - send data to classes for processing
         - send data to classes for saving
         '''
        # group fields by class
        formByClasses = self.__organizeFormByClasses(rdfForm)
        
        # get data of edited objects
        oldFormData = self.getFormData(rdfForm)
        idClassUri = oldFormData.get("formClassUri")
       #print("~~~~~~~~~ oldFormData: ",oldFormData)    
        # validate the form data for class requirements (required properties, 
        # security, valid data types etc)
        validation = self.__validateFormByClassRequirements(formByClasses, \
                rdfForm, oldFormData)
        if not validation.get('success'):
            print("%%%%%%% validation in saveForm",validation)
            return validation   
        # determine class save order
       #print("^^^^^^^^^^^^^^^ Passed VAlidation")
        classSaveOrder = self.__getSaveOrder(rdfForm)
        reverseDependancies = classSaveOrder.get("reverseDependancies",{})
        classSaveOrder = classSaveOrder.get("saveOrder",{})
        
        # save class data
        dataResults = []
        idValue = None
        for rdfClass in classSaveOrder:
            status = {}
            className = self.getClassName(rdfClass)
            status = getattr(self,className).save(formByClasses.get(\
                    className,[]),oldFormData)
            dataResults.append({"rdfClass":rdfClass,"status":status})
            if status.get("status")=="success":
                updateClass = reverseDependancies.get(rdfClass,[])
                if rdfClass == idClassUri:
                    idValue = cleanIri(\
                            status.get("lastSave",{}).get("objectValue"))
                for prop in updateClass:
                    found = False
                    for i, field in enumerate(
                        formByClasses.get(prop.get('className',''))):
                        if field.get('fieldJson', {}).get('propUri') ==\
                           prop.get('propUri',''):
                            found=True
                            class_name = prop.get('className','')
                            formByClasses[class_name][i]['data'] = \
                                status.get("lastSave",{}).get("objectValue")
                    if not found:
                        formByClasses[prop.get('className','')].append({
                            'data': status.get("lastSave",{}).get(\
                                        "objectValue"),
                            'fieldJson': self.getProperty(
                                className=prop.get("className"),
                                propName=prop.get("propName"))[0]})
        return  {"success":True, "classLinks":classSaveOrder, "oldFormData":\
                    oldFormData, "dataResults":dataResults, "idValue": idValue}
    
    def getPrefix(self, formatType="sparql"):
        ''' Generates a string of the rdf namespaces listed used in the 
            framework
        
            formatType: "sparql" or "turtle"
        '''
        returnStr = ""
        for ns in self.rdf_app_dict['application'].get("appNameSpace",[]):
            if formatType.lower() == "sparql":
                returnStr += "PREFIX {0}: {1}\n".format(
                                ns.get('prefix'),
                                iri(ns.get('nameSpaceUri')))
            elif formatType.lower() == "turtle":
                returnStr += "@prefix {0}: {1} .\n".format(
			                   ns.get('prefix'),
                               iri(ns.get('nameSpaceUri'))) 
        return returnStr
        
    def __loadApp(self): 
        if (self.app_initialized != True):
            appJson = self.__load_application_defaults()
            self.rdf_app_dict =  appJson
            # add attribute for a list of property processors that
            # will generate a property value when run
            valueProcessors = []
            for processor, value in \
                    appJson.get("PropertyProcessor",{}).items():
                if value.get("resultType") == "propertyValue":
                    valueProcessors.append(\
                        "http://knowledgelinks.io/ns/data-resources/%s" % \
                            (processor))
            self.valueProcessors = valueProcessors
            self.app_initialized = True      
    
    def __generateClasses(self):
        if (RdfFramework.class_initialized != True):
            classJson = self.__load_rdf_class_defintions()
            self.rdf_class_dict =  classJson
            RdfFramework.class_initialized = True 
            for c in self.rdf_class_dict:
                setattr(self, c, RdfClass(classJson[c],c))  
    
    def __generateForms(self):
        if (self.forms_initialized != True):
            formJson = self.__load_rdf_form_defintions()
            self.rdf_form_dict =  formJson
            self.form_initialized = True 
            '''for c in self.rdf_class_dict:
                setattr(self,c,rdf_class(classJson[c],c)) '''
    
    def __load_application_defaults(self):
        ''' Queries the triplestore for settings defined for the application in
            the kl_app.ttl file'''
        sparql = render_without_request(
            "jsonApplicationDefaults.rq",
            graph= "<http://knowledgelinks.io/ns/application-framework/>") 
                    #current_app.config.get('RDF_DEFINITION_GRAPH')) 
        formList =  requests.post(  
            current_app.config.get('TRIPLESTORE_URL'),
            data={"query": sparql,
                  "format": "json"})
       #print("***** Querying triplestore - Application Defaults ****")
        return json.loads(formList.json().get('results').get('bindings'\
                )[0]['app']['value'])
        
    def __load_rdf_class_defintions(self):
        ''' Queries the triplestore for list of classes used in the app as 
            defined in the kl_app.ttl file'''
        sparql = render_without_request(
            "jsonrdfClassDefinitions.rq",
            graph= "<http://knowledgelinks.io/ns/application-framework/>") 
            #current_app.config.get('RDF_DEFINITION_GRAPH')) 
        formList =  requests.post( 
            current_app.config.get('TRIPLESTORE_URL'),
            data={"query": sparql,
                  "format": "json"})
       #print("***** Querying triplestore - Class Definitions ****")
        return json.loads(formList.json().get('results').get('bindings'\
                )[0]['appClasses']['value'])
        
    def __load_rdf_form_defintions(self):
        ''' Queries the triplestore for list of forms used in the app as 
            defined in the kl_app.ttl file'''
        sparql = render_without_request(
            "jsonFormQueryTemplate.rq",
            graph= "<http://knowledgelinks.io/ns/application-framework/>") 
            #current_app.config.get('RDF_DEFINITION_GRAPH')) 
        classList =  requests.post( 
            current_app.config.get('TRIPLESTORE_URL'),
            data={"query": sparql,
                  "format": "json"})
       #print("***** Querying triplestore - Form Definitions ****")
        rawJson = classList.json().get('results').get('bindings'\
                )[0]['appForms']['value']
                
        return json.loads(rawJson.replace('"hasProperty":','"properties":'))
        
    def __organizeFormByClasses(self, rdfForm):
        ''' Arrange the form objects and data by rdf class for validation and 
            saveing'''
        returnObj = {}
        for row in rdfForm.rdfFieldList:
            for field in row:
                appendObj = {"fieldJson":field, "data":getattr(rdfForm,\
                            field.get("formFieldName")).data} 
                            #, "wtfield":getattr(rdfForm,\
                            #field.get("formFieldName"))}
                try:
                    returnObj[field.get('className')].append(appendObj)
                except:
                    returnObj[field.get('className')] = []
                    returnObj[field.get('className')].append(appendObj)
        return returnObj  
       
    def __getFormClassLinks(self, rdfForm):
        '''get linkages between the classes in the form'''
        returnObj = {}
        classSet = set()
        for row in rdfForm.rdfFieldList:
            for field in row:
                classSet.add(field.get('className'))
        dependantClasses = set()
        independantClasses = set()
        classDependancies = {}
        reverseDependancies = {}
        for rdfClass in classSet:
            currentClass = getattr(self,rdfClass)
            currentClassDependancies = currentClass.listDependant()
            classDependancies[rdfClass] = currentClassDependancies
            for reverseClass in currentClassDependancies:
                if not isinstance(reverseDependancies.get(reverseClass.get(\
                        "classUri","missing")),list):
                    reverseDependancies[reverseClass.get("classUri",\
                            "missing")] = []
                reverseDependancies[reverseClass.get("classUri","missing")\
                        ].append({
                        "className":rdfClass,
                        "propName":reverseClass.get("propName",""),
                        "propUri":reverseClass.get("propUri","")
                    })
            if len(currentClass.listDependant())>0:
                dependantClasses.add(currentClass.classUri)
            else:
                independantClasses.add(currentClass.classUri)
        returnObj = {"depClasses": list(dependantClasses),
                    "indepClasses": list(independantClasses),
                    "dependancies": classDependancies,
                    "reverseDependancies": reverseDependancies} 
        return returnObj          
        
    def __validateFormByClassRequirements(self, formByClasses, rdfForm, \
            oldFormData):
        '''This method will cycle thhrought the form classes and 
           call the classes validateFormData method and return the results'''
           
        validationResults = {}
        validationErrors = []
        for rdfClass in formByClasses:
            currentClass = getattr(self,rdfClass)
            validationResults = currentClass.validateFormData(\
                    formByClasses[rdfClass], oldFormData)
            if not validationResults.get("success",True):
                validationErrors += validationResults.get("errors",[])
        if len(validationErrors)>0:
            for error in validationErrors:
                for prop in makeList(error.get("errorData",{}).get(\
                        "propUri",[])):
                    formFieldName = self.__findFormFieldName(rdfForm,prop)
                    if formFieldName:
                        formProp = getattr(rdfForm,formFieldName)
                        if hasattr(formProp,"errors"):
                            formProp.errors.append(error.get(\
                                    "formErrorMessage"))
                        else:
                            setattr(formProp,"errors",[error.get(\
                                    "formErrorMessage")])
            
                   
            return {"success": False, "form":rdfForm, "errors": \
                        validationErrors}
        else:
            return {"success": True}
                
    def __findFormFieldName(self,rdfForm,propUri):
        for row in rdfForm.rdfFieldList:
            for prop in row:
                if prop.get("propUri") == propUri:
                    return prop.get("formFieldName")
        return None
                
    def getFormData(self, rdfForm, **kwargs):
        ''' returns the data for the current form paramters
        
        **keyword arguments
        subjectUri: the URI for the subject
        classUri: the rdf class of the subject
        '''
        #print(kwargs)
        classUri = kwargs.get("classUri",rdfForm.dataClassUri)
        lookupClassUri = classUri
        #print(rdfForm.__dict__)
        #print("classUri: ",classUri)
        className = self.getClassName(classUri)
        #print("className: ", className)
        subjectUri = kwargs.get("subjectUri",rdfForm.dataSubjectUri)
        #print("subjectUri: ",subjectUri)
        sparqlArgs = None
        classLinks = self.__getFormClassLinks(rdfForm)
        sparqlConstructor = dict.copy(classLinks['dependancies'])
        
        baseSubjectFinder = None
        linkedClass = None
        linkedProp = False
        sparqlElements = []
        if IsNotNull(subjectUri):
            # find the primary linkage between the supplied subjectId and 
            # other form classes
            for rdfClass in sparqlConstructor:
                for prop in sparqlConstructor[rdfClass]: 
                    try:
                        if classUri == prop.get("classUri"):
                            sparqlArgs = prop
                            linkedClass = rdfClass
                            sparqlConstructor[rdfClass].remove(prop)
                            if rdfClass != lookupClassUri:
                                linkedProp = True
                                
                    except:
                        x = 0
           #print(json.dumps(sparqlConstructor ,indent=4))
            # generate the triple pattern for linked class
            if sparqlArgs:
                baseSubjectFinder = \
                        "BIND({} AS ?baseSub) .\n\t{}\n\t{}".format(
                        iri(subjectUri),                                        
                        makeTriple("?baseSub","a",iri(lookupClassUri)),
                        makeTriple("?classID",iri(sparqlArgs.get("propUri")),\
                        "?baseSub"))
               #print("base subject Finder:\n",baseSubjectFinder) 
                if linkedProp:
                    sparqlElements.append(\
                            '''BIND({} AS ?baseSub) .\n\t{}\n\t{}
\t?s ?p ?o .'''.format(iri(subjectUri),                                        
                            makeTriple("?baseSub","a",iri(lookupClassUri)),
                            makeTriple("?s",iri(sparqlArgs.get("propUri")),\
                            "?baseSub")))
            # iterrate though the classes used in the form and generate the 
            # spaqrl triples to pull the data for that class
            for rdfClass in sparqlConstructor:
                if rdfClass == className:
                    sparqlElements.append(\
                            "\tBIND({} AS ?s) .\n\t{}\n\t?s ?p ?o .".format(
                           iri(subjectUri),
                           makeTriple("?s","a",iri(lookupClassUri))))
                for prop in sparqlConstructor[rdfClass]:
                    if rdfClass == className:
                        #sparqlElements.append("\t"+makeTriple(iri(str(\
                                #subjectUri)),iri(prop.get("propUri")),"?s")+\
                                # "\n\t?s ?p ?o .")
                        sparqlArg = '''\tBIND({} AS ?baseSub) .\n\t{}
\t{}\n\t?s ?p ?o .'''.format(iri(subjectUri),
                                makeTriple("?baseSub","a",iri(lookupClassUri)),
                                makeTriple("?baseSub",iri(prop.get(\
                                "propUri")),"?s")) 
                        #print("!!!!! className=rdfClass: ",rdfClass, \
                        #" -- element: \n",sparqlArg)
                        sparqlElements.append(sparqlArg)
                    elif rdfClass == linkedClass:
                        sparqlElements.append(
                            "\t{}\n\t{}\n\t?s ?p ?o .".format(
                                baseSubjectFinder,
                                makeTriple("?classID",iri(prop.get(\
                                        "propUri")),"?s")))
                    
                    
                    '''**** The case where an ID looking up a the triples for 
                        a non-linked related is not functioning i.e. password 
                        ClassID not looking up person org triples if the org 
                        class is not used in the form. This may not be a 
                        problem ... the below comment out is a start to solving
                         if it is a problem
                        
                        elif linkedClass != self.getClassName(prop.get(\
                                "classUri")):
                        sparqlElements.append(
                            "\t" +baseSubjectFinder + "\n " +
                            "\t"+ makeTriple("?classID",iri(prop.get(\
                                    "propUri")),"?s") + "\n\t?s ?p ?o .")'''
                            
            # merge the sparql elements for each class used into one combine 
            # sparql union statement
            sparqlUnions = "{{\n{}\n}}".format("\n} UNION {\n".join(\
                    sparqlElements))
            
            # render the statment in the jinja2 template
            sparql = render_without_request(
                "sparqlItemTemplate.rq",
                prefix = self.getPrefix(),
                query = sparqlUnions) 
           #print (sparql)
            # query the triplestore
            code_timer().log("loadOldData","pre send query")
            formDataQuery =  requests.post( 
                current_app.config.get('TRIPLESTORE_URL'),
                data={"query": sparql,
                      "format": "json"})
            code_timer().log("loadOldData","post send query")
           #print(json.dumps(formDataQuery.json().get('results').get(\
                    #'bindings'),indent=4))
            queryData = convertSPOtoDict(formDataQuery.json().get('results'\
                    ).get('bindings'))
            code_timer().log("loadOldData","post convert query")
            print("form query data _____\n",json.dumps(queryData,indent=4))
            #queryData = formDataQuery.json().get('results').get('bindings')
            #queryData = json.loads(formDataQuery.json().get('results').get(
            #'bindings')[0]['itemJson']['value']) 
        else:
            queryData = {}
        # compare the return results with the form fields and generate a 
        # formData object
        formData = {}

        for row in rdfForm.rdfFieldList:
            for prop in row:
                #print(prop,"\n\n")
                pUri = prop.get("propUri")
                cUri = prop.get("classUri")
                #print(cUri," ",pUri,"\n\n")
                dataValue = None
                for subject in queryData:
                    if cUri in queryData[subject].get( \
                            "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"):
                        dataValue = queryData[subject].get(prop.get("propUri"))
                if dataValue:
                    processors = clean_processors(
                                    makeList(prop.get("processors")), cUri)
                    print("processors - ", pUri, " - ",processors,\
                            "\npre - ",makeList(prop.get("processors")))
                    for processor in processors:
                        dataValue = run_processor(processor,
                                            {"propUri": pUri,
                                            "classUri": cUri,
                                            "prop": prop,
                                            "queryData": queryData,
                                            "dataValue": dataValue},
                                            "load")
                        
                formData[prop.get("formFieldName")]=dataValue
        formDataDict = MultiDict(formData)
        code_timer().log("loadOldData","post load into MultiDict")
        #print("data:\n",formData)
        #print("dataDict:\n",formDataDict)
        code_timer().printTimer("loadOldData",delete=True)
        return {"formdata":formDataDict,
                "queryData":queryData,
                "formClassUri":lookupClassUri}
            
    def __getSaveOrder(self, rdfForm):
        '''Cycle through the classes and determine in what order they need 
           to be saved
           1. Classes who's properties don't rely on another class 
           2. Classes that that depend on classes in step 1
           3. Classes stored as blanknodes of Step 2 '''   
        classLinks = self.__getFormClassLinks(rdfForm) 
        #print(json.dumps(classLinks,indent=4))
        saveOrder = []
        saveLast = []
        for rdfClass in classLinks.get("indepClasses",[]):
            saveOrder.append(rdfClass)
        for rdfClass in classLinks.get("depClasses",[]):
            dependant = True
            className = self.getClassName(rdfClass)
            for depClass in classLinks.get("dependancies",{}):
                if depClass != className:
                    for prop in classLinks.get("dependancies",{}\
                            ).get(depClass,[]):
                        #print(className," d:",depClass," r:",rdfClass," p:",
                        #prop.get('classUri'))
                        if prop.get('classUri')==rdfClass:
                            dependant = False
            if not dependant:
                saveOrder.append(rdfClass)
            else:
                saveLast.append(rdfClass)       
        return {"saveOrder":saveOrder + saveLast,
                "reverseDependancies":classLinks.get("reverseDependancies",{})}
        
class RdfClass(object):
    '''RDF Class for an RDF Class object. 
       Used for manipulating and validating an RDF Class subject'''
       
    def __init__(self, jsonObj, className):
        for p in jsonObj:
            setattr(self, p, jsonObj[p])
        setattr(self, "className", className)
    
    def save(self, rdf_form, old_form_data,validationStatus=False):
        """Method validates and saves passed data for the class

        Args:
            rdf_form -- Current RDF Form class fields
            old_form_data -- Preexisting form data
            validationS
        """
        '''validRequiredProps = self.__validateRequiredProperties(
            rdf_form,
            old_form_data)
        validDependancies = self.__validateDependantProperties(
            rdf_form,
            old_form_data)'''
        save_data = self.__processClassData(
            rdf_form,
            old_form_data)
        save_query = self.__generateSaveQuery(save_data)
        return self.__runSaveQuery(save_query)

        
    def newUri(self):
        '''*** to be written ***
        generates a new URI 
          -- for fedora generates the container and returns the URI
          -- for blazegraph process will need to be created'''
       #print("generating new URI")
        
    def validateFormData(self, rdfForm, oldFormData):
        '''This method will validate whether the supplied form data 
           meets the class requirements and returns the results''' 
        validationSteps = {}   
        validationSteps['validRequiredFields'] = \
                self.__validateRequiredProperties(rdfForm,oldFormData)
        validationSteps['validPrimaryKey'] = \
                self.validatePrimaryKey(rdfForm,oldFormData)
        validationSteps['validFieldData'] = \
                self.__validatePropertyData(rdfForm,oldFormData)
        validationSteps['validSecurity'] =  \
                self.__validateSecurity(rdfForm,oldFormData)
        #print("----------------- Validation ----------------------\n",\
                #json.dumps(validationSteps,indent=4))
        validationErrors = []
        for step in validationSteps:
            if validationSteps[step][0] != "valid":
               for error in validationSteps[step]:
                    validationErrors.append(error)
        if len(validationErrors)>0:
            return {"success": False, "errors":validationErrors}
        else: 
            return {"success": True}
        
    def validatePrimaryKey(self, rdfForm,oldData={}):
        '''query to see if PrimaryKey is Valid'''
        
        returnVal = False #! This variable is never used
        queryStr = ""
        try:
            pkey = makeList(self.primaryKey)
            #print(self.classUri," PrimaryKeys: ",pkey,"\n")
            if len(pkey)<1:
                return "valid"
            else:
                calculatedProps = self.__getCalculatedProperties()
                oldClassData = self.__selectClassQueryData(oldData)
                #print("pkey oldClassData: ",oldClassData,"\n\n")
                newClassData = {}
                queryArgs = [makeTriple("?uri","a",iri(self.classUri))]
                multiKeyQueryArgs = [makeTriple("?uri","a",iri(self.classUri))]
                keyChanged = False
                fieldNameList = []
                # get primary key data from the form data
                for prop in rdfForm:
                    if prop['fieldJson'].get("propUri") in pkey:
                        newClassData[prop['fieldJson'].get("propUri")] = \
                                prop['data']
                        fieldNameList.append(prop['fieldJson'].get( \
                                "formLabelName",''))
                #print("pkey newClassData: ",newClassData,"\n\n")
                for key in pkey:
                    print ("********************** entered key loop")
                    print("old-new: ",oldClassData.get(key)," -- ",
                                                    newClassData.get(key),"\n")
                    objectVal = None
                    #get the dataValue to test against
                    dataValue = newClassData.get(key,oldClassData.get(key))
                    print("dataValue: ",dataValue)
                    if IsNotNull(dataValue):
                        print ("********************** entered dataValue if",
                                       "-- propName: ", self.findPropName(key))
                        
                        dataType = self.properties.get(self.findPropName(key)\
                                ).get("range",[])[0].get('storageType')
                        print("dataType: ",dataType)
                        if dataType == 'literal':
                            dataType = self.properties.get(self.findPropName( \
                                    key)).get("range",[])[0].get('rangeClass')
                            objectVal = RdfDataType(dataType).sparql(dataValue)
                        else:
                            objectVal = iri(dataValue)
                    print("objectVal: ",objectVal)
                    # if the oldData is not equel to the newData re-evaluate 
                    # the primaryKey                        
                    if (oldClassData.get(key) != newClassData.get(key)) and \
                        (key not in calculatedProps):
                        keyChanged = True
                        if objectVal:
                            queryArgs.append(makeTriple("?uri", iri(key), \
                                    objectVal))
                            multiKeyQueryArgs.append(makeTriple("?uri", \
                                    iri(key), objectVal))
                    else:
                        if objectVal:
                            multiKeyQueryArgs.append(makeTriple("?uri", \
                                    iri(key), objectVal))
                print("\n////////////////// queryArgs:\n",queryArgs)
                print("               multiKeyQueryArgs:\n",multiKeyQueryArgs)
                print("               keyChanged: ",keyChanged)         
                if keyChanged:
                    #print("Enter keyChanged")
                    if len(pkey)>1:
                        args = multiKeyQueryArgs
                    else:
                        args = queryArgs
                    sparql = '''{}\nSELECT (COUNT(?uri)>0 AS ?keyViolation)
{{\n{}\n}}\nGROUP BY ?uri'''.format(
                                get_framework().getPrefix(),
                                "\n".join(args))
                    #print(sparql)
                    keyTestResults =  requests.post( 
                                        current_app.config.get( \
                                                'TRIPLESTORE_URL'),
                                        data={"query": sparql,
                                              "format": "json"})
                    #print("keyTestResults: ",keyTestResults.json())
                    keyTest = keyTestResults.json().get('results').get( \
                            'bindings',[])
                    #print(keyTest)
                    #print(json.dumps(keyTest[0],indent=4))
                    if len(keyTest)>0:
                        keyTest = keyTest[0].get('keyViolation',{}).get( \
                                'value',False)
                    else:
                        keyTest = False            
                    
                    #print("----------- PrimaryKey query:\n",sparql)
                    if not keyTest:
                        return ["valid"]
                    else:
                        return [{"errorType":"primaryKeyViolation",
                                 "formErrorMessage": \
                                        "This {} aleady exists.".format(
                                    " / ".join(fieldNameList)),                                    
                                    "errorData":{
                                        "class":self.classUri,
                                        "propUri":pkey}}]
                return ["valid"]
        except:
            return ["valid"]
        else:
            return ["valid"]
            
    def listRequired(self):
        '''Returns a set of the required properties for the class'''
        requiredList = set()
        for p in self.properties:
            if self.properties[p].get('requiredByDomain') == self.classUri:
                requiredList.add(self.properties[p].get('propUri'))
        try:
            if type(self.primaryKey) == "list":
                for key in self.primaryKey:
                    requiredList.add(key)
            else:
                requiredList.add(self.primaryKey)
        except:
            x = None
        return requiredList
                
    def listProperties(self):
        '''Returns a dictionary of the properties used for the class'''
        property_list = set()
        for p in self.properties:
            property_list.add(self.properties[p].get('propUri'))
        return property_list 
            
    def listDependant(self):
        '''Returns a set of properties that are dependent upon the 
        creation of another object'''
        dependent_list = set()
        for prop in self.properties:
            range_list = self.properties[prop].get('range')
            for row in range_list: 
                if row.get('storageType') == "object" or \
                   row.get('storageType') == "blanknode":
                    dependent_list.add(prop)
        return_obj = []
        for dep in dependent_list:
            range_list = self.properties[dep].get('range')
            for row in range_list: 
                if row.get('storageType') == "object" or \
                   row.get('storageType') == "blanknode":
                    return_obj.append(
                       {"propName": dep, 
                        "propUri": self.properties[dep].get("propUri"), 
                        "classUri": row.get("rangeClass")})
        return return_obj
        
    def findPropName (self,propUri):
        "cycle through the class properties object to find the property name"
        #print(self.properties)
        try:
            for p in self.properties:
                #print("p--",p," -- ",self.properties[p]['propUri'])
                if self.properties[p]['propUri'] == propUri:
                   ##print ('propName is ',p)
                    return p
        except:
            return None
    
    def getProperty (self,**kwargs):
        '''Method returns the property json object
        
        keyword Args:
            propName: The Name of the property
            propUri: The URI of the property
            ** the PropName or URI is required'''
        
        propName = kwargs.get("propName")
        propUri = kwargs.get("propUri")    
        #print(self.properties)
        if propUri:
            propName = self.findPropName(propUri)
        #print(self.__dict__)
        try:
            return self.properties.get(propName)
        except:
            return None

            
    def __validateRequiredProperties (self,rdfForm,oldData):
        '''Validates whether all required properties have been supplied and 
            contain data '''
        returnError = []
        #create sets for evaluating requiredFields
        required = self.listRequired()
        dataProps = set()
        deletedProps = set()
        for prop in rdfForm:
            #remove empty data properties from consideration
            if IsNotNull(prop['data']) or prop['data'] != 'None':
                dataProps.add(prop['fieldJson'].get("propUri"))
            else:
                deletedProps.add(prop['fieldJson'].get("propUri"))
        # find the properties that already exist in the saved class data
        oldClassData = self.__selectClassQueryData(oldData)
        for prop in oldClassData:
            # remove empty data properties from consideration  
            if IsNotNull(oldClassData[prop]) or oldClassData[prop] != 'None':
                ##print(">>>>>> oldClassData: ", p)
                dataProps.add(prop)
        # remove the deletedProps from consideration and add calculated props
        #print("------- dataProps: ", dataProps)
        validProps = (dataProps - deletedProps).union( \
                self.__getCalculatedProperties())
        #print("---------calcprops: ",self.__getCalculatedProperties())
        #Test to see if all the required properties are supplied    
        missingRequiredProperties = required - validProps
        #print("@@@@@ missingRequiredProperties: ",missingRequiredProperties)
        if len(missingRequiredProperties)>0:
            returnError.append({
                "errorType":"missingRequiredProperties",
                "errorData":{
                    "class":self.classUri,
                    "properties":makeList(missingRequiredProperties)}})
        if len(returnError)>0:
            returnVal =  returnError
        else:
            returnVal =  ["valid"]
        #print("__validateRequiredProperties - ", self.classUri, " --> ",\
                #returnVal)
        return returnVal
        
    def __getCalculatedProperties(self):
        '''lists the properties that will be calculated if no value is 
           supplied'''
        calcList = set()
        
        valueProcessors = get_framework().valueProcessors
        #print("valueProcessors: ",valueProcessors)
        for p in self.properties:
            # Any properties that have a default value will be generated at 
            # time of save
            if IsNotNull(self.properties[p].get('defaultVal')):
                calcList.add(self.properties[p].get('propUri'))
            processors = makeList(self.properties[p].get('propertyProcessing',\
                    []))
            # find the processors that will generate a value
            for processor in processors:
                #print("processor: ",processor) 
                if processor in valueProcessors:
                    
                    calcList.add(self.properties[p].get('propUri'))
        #any dependant properties will be generated at time of save
        dependentList = self.listDependant()
        for prop in dependentList:
            calcList.add(prop.get("propUri"))
        return calcList      
          
    def __validateDependantProperties(self, rdfForm,oldData):
        '''Validates that all supplied dependant properties have a uri as an 
            object'''
        dep = self.listDependant()
        returnError = []
        dataProps = set()
        for p in rdfForm:
            #remove empty data properties from consideration
            if IsNotNull(p['data']):
                dataProps.add(self.findPropName(p['fieldJson'].get("propUri")))
        '''for p in dep:
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
        if len(returnError) > 0:
            return returnError
        else:'''
        return ["valid"]       
    
    def __selectClassQueryData(self,oldData):
        '''Find the data in query data that pertains to this class instance
        
        returns dictionary of data with the subjectUri stored as 
                !!!!subject'''
                
        #print("__________ class queryData:\n",\
        #                        json.dumps(dumpable_obj(oldData),indent=4))
        oldClassData = {}
        if oldData.get("queryData"):
            # find the cuurent class data from in the query
            for subjectUri in oldData.get("queryData"):
                ##print("\t\t subjectUri: ",subjectUri," subjectClass: ",\
                #oldData['queryData'][subjectUri].get(\
                    #"http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
                #    "\n \t\t\tclassUri: ",self.classUri)
                classTypes = makeList(oldData['queryData'][subjectUri].get( \
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",[]))
                for rdfType in classTypes:
                    classTest = iri(self.classUri)
                    if rdfType == classTest:
                        oldClassData = oldData['queryData'][subjectUri]
                        oldClassData["!!!!subjectUri"] = subjectUri
                    break
        print("ttttttttttttt oldClassData:\n",\
                               json.dumps(dumpable_obj(oldClassData),indent=4))
        return oldClassData
        
    def __validatePropertyData(self,rdfForm,oldData):
        return ["valid"]
        
    def __validateSecurity(self,rdfForm,oldData):
        return ["valid"]

    def __processClassData(self,rdfForm,oldDataObj):
        '''Reads through the processors in the defination and processes the 
            data for saving'''
        preSaveData={}
        saveData={}
        processedData={}
        obj={}
        requiredProps = self.listRequired()
        calculatedProps = self.__getCalculatedProperties()
        oldData = self.__selectClassQueryData(oldDataObj)
        subjectUri = oldData.get("!!!!subjectUri","<>")
        # cycle through the form class data and add old, new, doNotSave and
        # processors for each property
        print("****** oldData:\n",json.dumps(dumpable_obj(oldData),indent=4))
        for prop in rdfForm:
            propUri = prop.get('fieldJson',{}).get('propUri')
            # gather all of the processors for the proerty
            classProp = self.getProperty(propUri=prop['fieldJson'].get( \
                        "propUri"))
            classPropProcessors = set(clean_processors(makeList(\
                    classProp.get("propertyProcessing"))))
            formPropProcessors = set(clean_processors(makeList(\
                    prop['fieldJson'].get("processors"))))
            processors = remove_null(\
                                classPropProcessors.union(formPropProcessors))
            # remove the property from the list of required properties
            # required properties not in the form will need to be addressed
            requiredProp = False
            if propUri in requiredProps:
                requiredProps.remove(propUri)
                requiredProp = True
            # remove the property from the list of calculated properties
            # calculated properties not in the form will need to be addressed
            if propUri in calculatedProps:
                calculatedProps.remove(propUri)
            # add the information to the preSaveData object
            if not preSaveData.get(propUri):
                preSaveData[propUri] = {"new":prop.get('data'),
                                "old":oldData.get(propUri),
                                "className": self.className,
                                "required": requiredProp,
                                "editable": prop['fieldJson'].get(\
                                                "editable",True),
                                "doNotSave": prop['fieldJson'].get(\
                                                "doNotSave",False),
                                "processors": processors}
            else:
                #print("#########################",propUri,"--",\
                            #preSaveData[propUri])
                tempList = makeList(preSaveData[propUri])
                tempList.append({"new":prop.get('data'),
                                "old":oldData.get(propUri),
                                "className": self.className,
                                "required": requiredProp,
                                "editable": prop['fieldJson'].get(\
                                                "editable",True),
                                "doNotSave": prop['fieldJson'].get(\
                                        "doNotSave",False),
                                "processors": processors})
                preSaveData[propUri] = tempList
        # now deal with missing required properties. cycle through the 
        # remaing properties and add them to the preSaveData object
        for propUri in requiredProps:
            print("########### requiredProps: ")
            classProp = self.getProperty(propUri=propUri)
            print(classProp)
            classPropProcessors = remove_null(makeSet(\
                            clean_processors(makeList(\
                                    classProp.get("propertyProcessing")))))
            # remove the prop from the remaining calculated props
            if propUri in calculatedProps:
                calculatedProps.remove(propUri)
            if not preSaveData.get(propUri):
                preSaveData[propUri] = {"new":NotInFormClass(),
                                        "old":oldData.get(propUri),
                                        "doNotSave":False,
                                        "className": self.className,
                                        "required": True,
                                        "editable": True,
                                        "processors":classPropProcessors,
                                        "defaultVal":classProp.get(\
                                                "defaultVal"),
                                        "calculation": classProp.get(\
                                                "calculation")}
                print("psave: ",preSaveData[propUri])
            else:
                tempList = makeList(preSaveData[propUri])
                preSaveData[propUri] = tempList.append({"new":NotInFormClass(),
                                        "old":oldData.get(propUri),
                                        "doNotSave": False,
                                        "className": self.className,
                                        "editable": True,
                                        "processors":classPropProcessors,
                                        "defaultVal":classProp.get(\
                                                "defaultVal"),
                                        "calculation": classProp.get(\
                                                "calculation")})
        # now deal with missing calculated properties. cycle through the 
        # remaing properties and add them to the preSaveData object
        print("calc props: ",calculatedProps)
        for propUri in calculatedProps:
            print("########### calculatedProps: ")
            classProp = self.getProperty(propUri=propUri)
            classPropProcessors = remove_null(makeSet(\
                            clean_processors(makeList(\
                                    classProp.get("propertyProcessing")))))
            if not preSaveData.get(propUri):
                preSaveData[propUri] = {"new":NotInFormClass(),
                                        "old":oldData.get(propUri),
                                        "doNotSave":False,
                                        "processors":classPropProcessors,
                                        "defaultVal":classProp.get(\
                                                "defaultVal"),
                                        "calculation": classProp.get(\
                                                "calculation")}
            else:
                tempList = makeList(preSaveData[propUri])
                preSaveData[propUri] = tempList.append({"new":NotInFormClass(),
                                        "old":oldData.get(propUri),
                                        "doNotSave":False,
                                        "processors":classPropProcessors,
                                        "defaultVal":classProp.get(\
                                                "defaultVal"),
                                        "calculation": classProp.get(\
                                                "calculation")})  
        #print(json.dumps(dumpable_obj(preSaveData),indent=4)) 
        print("_________________________________________________")
        # cycle through the consolidated list of preSaveData to
        # test the security, run the processors and calculate any values   
        for propUri, prop in preSaveData.items():
            # ******* doNotSave property is set during form field creation
            # in getWtFormField method. It tags fields that are there for
            # validation purposes i.e. password confirm fields ******
            
            if isinstance(prop,list):
                # a list with in the property occurs when there are 
                # multiple fields tied to the property. i.e. 
                # password creation or change / imagefield that 
                # takes a URL or file
                for propInstance in prop:
                    if propInstance.get("doNotSave",False):
                        preSaveData[propUri].remove(propInstance)
                if len(makeList(preSaveData[propUri]))==1:
                    preSaveData[propUri] = preSaveData[propUri][0]
            #doNotSave = prop.get("doNotSave",False)
        for propUri, prop in preSaveData.items():    
            # send each property to be proccessed
            if prop:
                obj = self.__processProp({"propUri":propUri,
                                            "prop": prop,
                                            "processedData": processedData,
                                            "preSaveData": preSaveData})
                processedData = obj["processedData"]
                preSaveData = obj["preSaveData"]
        
        saveData = {
                "data":self.__format_data_for_save(processedData,preSaveData),
                "subjectUri":subjectUri}
                    
        #print(json.dumps(dumpable_obj(preSaveData),indent=4))
         
        return saveData
                   
    def __generateSaveQuery(self,saveDataObj,subjectUri=None):
        saveData = saveDataObj.get("data")
        # find the subjectUri positional argument or look in the saveDataObj
        # or return <> as a new node 
        if not subjectUri:
            subjectUri = iri(saveDataObj.get('subjectUri',"<>"))
        saveType = self.storageType
        if subjectUri == "<>" and saveType.lower() == "blanknode":
            saveType = "blanknode"
        else:
            saveType = "object"
        bnInsertClause = []
        insertClause = ""
        deleteClause = ""
        whereClause = ""
        propSet = set()
        i = 1
        print("save data in generateSaveQuery\n",json.dumps(\
                                            dumpable_obj(saveData),indent=4),
                                            "\n",saveData)
        # test to see if there is data to save                                    
        if len(saveData)>0:
            for prop in saveData:
                propSet.add(prop[0])
                propIri = iri(prop[0])
                if not isinstance(prop[1], DeleteProperty):
                    insertClause += "{}\n".format(\
                                        makeTriple(subjectUri,propIri,prop[1]))
                    bnInsertClause.append("\t{} {}".format(propIri,prop[1]))    
            if subjectUri != '<>':
                for prop in propSet:
                    propIri = iri(prop)
                    deleteClause += "{}\n".format(\
                                    makeTriple(subjectUri,propIri,"?"+str(i)))
                    whereClause += "OPTIONAL {{ {} }} .\n".format(\
                                    makeTriple(subjectUri,propIri,"?"+str(i)))
                    i += 1
            else:
                insertClause += makeTriple(subjectUri,"a",iri(self.classUri)) + \
                        "\n"
                bnInsertClause.append("\t a {}".format(iri(self.classUri)))
            if saveType == "blanknode":
                saveQuery = "[\n{}\n]".format(";\n".join(bnInsertClause))
            else:
                if subjectUri != '<>':
                    save_query_template = Template("""{{ prefix }}
                                    DELETE \n{
                                    {{ deleteClause }} }
                                    INSERT \n{
                                    {{ insertClause }} }
                                    WHERE \n{
                                    {{ whereClause }} }""")
                    saveQuery = save_query_template.render(
                        prefix=get_framework().getPrefix(), 
                        deleteClause=deleteClause,
                        insertClause=insertClause,
                        whereClause=whereClause)
                else:
                    saveQuery = "{}\n\n{}".format(
                        get_framework().getPrefix("turtle"),
                        insertClause)
            print(saveQuery)
            return {"query":saveQuery,"subjectUri":subjectUri}
        else:
            return {"subjectUri":subjectUri}
        
    def __runSaveQuery(self, saveQueryObj,subjectUri=None):
        saveQuery = saveQueryObj.get("query")
        if not subjectUri:
            subjectUri = saveQueryObj.get("subjectUri")
       
        if saveQuery:
            if saveQuery[:1] == "[":
                object_value = saveQuery
            else:
                #! Should use PATCH if fedora object already exists, otherwise need 
                #! to use POST method. Should try to retrieve subject URI from 
                #! Fedora?
                if subjectUri == "<>":
                    repository_result = requests.post(
                        current_app.config.get("REPOSITORY_URL"),
                        data=saveQuery,
        				headers={"Content-type": "text/turtle"})
                    object_value = repository_result.text
                else:
                    repository_result = requests.patch(
                        cleanIri(subjectUri),
                        data=saveQuery,
        				headers={"Content-type": "application/sparql-update"})
                    object_value = iri(subjectUri)
            return {"status": "success",
                    "lastSave": {
                        "objectValue": object_value}
                   }
        else:
            return {"status": "success",
                    "lastSave": {
                        "objectValue": iri(subjectUri),
                        "comment": "No data to Save"}
                   }
    
    def findPropName (self,propUri):
        "cycle through the class properties object to find the property name"
        #print(self.properties)
        for p in self.properties:
            #print("p--",p," -- ",self.properties[p]['propUri'])
            if self.properties[p]['propUri'] == propUri:
                return p
    
    def __processProp(self,obj):
        # obj = propUri, prop, processedData, preSaveData
        if len(makeList(obj['prop']))>1:
            obj = self.__merge_prop(obj)
        processors = obj['prop'].get("processors",[])
        propUri = obj['propUri']
        # process properties that are not in the form
        if isinstance(obj['prop'].get("new"), NotInFormClass):
            # process required properties
            if obj['prop'].get("required"):
                # run all processors: the processor determines how to
                # handle if there is old data               
                if len(processors)>0:
                    for processor in processors:
                        obj = run_processor(processor, obj)
                # if the processors did not calculate a value for the
                # property attempt to calculte from the default 
                # property settings
                if not obj['prop'].get('calcValue',False):
                    obj = self.__calculate_property(obj)
            #else:
                # need to decide if you want to calculate properties
                # that are not required and not in the form
        # if the property is editable process the data        
        elif obj['prop'].get("editable"):
            # if the old and new data are different
            print (obj['prop'].get("new")," != ",obj['prop'].get("old"))
            if cleanIri(obj['prop'].get("new")) != \
                                    cleanIri(obj['prop'].get("old")):
                print("true")
                # if the new data is null and the property is not
                # required mark property for deletion
                if not IsNotNull(obj['prop'].get("new")) and not \
                                                obj['prop'].get("required"):
                    obj['processedData'][propUri] = DeleteProperty()
                # if the property has new data
                elif IsNotNull(obj['prop'].get("new")):
                    if len(processors)>0:
                        for processor in processors:
                            obj = run_processor(processor,obj)
                        if not obj['prop'].get('calcValue',False):
                            obj['processedData'][propUri] = \
                                                       obj['prop'].get("new")
                    else:
                        obj['processedData'][propUri] = obj['prop'].get("new")
                        
        return obj
    def __calculate_property(self,obj):
        ''' Reads the obj and calculates a value for the property'''
        return obj
                    
    def __merge_prop(self,obj):
        '''This will need to be expanded to handle more cases right now
        the only case is an image '''
        propList = obj['prop']
        keepImage = -1
        for i, prop in enumerate(obj['prop']):
            keepImage = i
            if isinstance(prop['new'],FileStorage):
                if prop['new'].filename:                 
                    break
        for i, prop in enumerate(obj['prop']):
            if i != keepImage:
                obj['prop'].remove(prop)
        obj['prop'] = obj['prop'][0]
        return obj    
        '''propList = obj['prop']
        classProp = self.getProperty(propUri=obj['propUri'])
        propRange = classProp.get('''
        '''for prop in propList:
            for name,attribute in prop.items():
                if conflictingValues.get(name):
                    if isinstance(conflictingValues.get(name),list):
                        if not attribute in conflictingValues.get(name):
                            conflictingValues[name].append(attribute)
                    elif conflictingValues.get(name) != attribute:
                        conflictingValues[name] = [conflictingValues[name],
                                                   attribute]
                else:
                    conflictingValues[name] = attribute'''
    def __format_data_for_save(self,processedData,preSaveData):
        saveData = []
        print("format data***********\n",json.dumps(dumpable_obj(processedData),indent=4))
        for propUri, prop in processedData.items():
            if isinstance(prop,DeleteProperty):
                saveData.append([propUri,prop])
            elif isinstance(prop,FileStorage):
                fileIri = save_file_to_repository(prop,
                                preSaveData[propUri][0].get('old')) 
                saveData.append([propUri,fileIri])
            else:
                propName = self.findPropName(propUri)
                dataType = self.properties[propName].get("range",[{}])[0].get(\
                                                                'storageType')
                if dataType == 'literal':
                    dataType = self.properties[propName].get(\
                                "range",[{}])[0].get('rangeClass',dataType)
                valueList = makeList(prop)
                for item in valueList:
                    if dataType in ['object','blanknode']:
                        saveData.append([propUri,iri(item)])
                    else:
                        saveData.append([propUri,RdfDataType(\
                                    dataType).sparql(str(item))])
        return saveData

class RdfDataType(object):
    "This class will generate a rdf data type"

    def __init__(self, RdfDataType):
        self.lookup = RdfDataType
        #! What happens if none of these replacements? 
        val = self.lookup.replace(str(XSD),"").\
                replace("xsd:","").\
                replace("rdf:","").\
                replace(str(RDF),"")
        if "http" in val:
            val = "string"
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
    
def iri(uriString):
    "converts a string to an IRI or returns an IRI if already formated"
    if uriString[:1] == "[":
        return uriString
    if uriString[:1] != "<":
        uriString = "<{}".format(uriString.strip())
    if uriString[len(uriString)-1:] != ">":
        uriString = "{}>".format(uriString.strip()) 
    return uriString

def IsNotNull(value):
    return value is not None and len(str(value)) > 0
    
def IsValidObject(uriString):
    '''Test to see if the string is a object store'''
    return True

def run_processor(processor, obj, mode="save"):
    '''runs the passed in processor and returns the saveData'''
    processor = processor.replace(\
            "http://knowledgelinks.io/ns/data-resources/","kdr:")

    if processor == "kdr:SaltProcessor":
        return salt_processor(obj, mode)
		
    elif processor == "kdr:PasswordProcessor":
        return password_processor(obj, mode)
    
    elif processor == "kdr:CalculationProcessor":
        return calculation_processor(obj, mode)
    
    elif processor == "kdr:CSVstringToMultiPropertyProcessor":
        return csv_string_to_multi_property_processor(obj, mode)
    	
    elif processor == "kdr:AssertionImageBakingProcessor":
        return assertion_image_baking_processor(obj, mode)
    	
    elif processor == "kdr:EmailVerificationProcessor":
        return email_verification_processor(obj, mode)
    
    else:
        if mode == "load":
            return obj.get("dataValue")
        elif mode == "save":
            return obj
        return obj
         
def assertion_image_baking_processor(obj, mode="save"):
    ''' Application sends badge image to the a badge baking service with the 
        assertion.'''
    if mode == "load":
        return obj.get("dataValue")
    return obj
    
def csv_string_to_multi_property_processor(obj, mode="save"):
    ''' Application takes a CSV string and adds each value as a seperate triple 
        to the class instance.'''
    if mode == "save":
        valueString = obj['prop']['new']
        if IsNotNull(valueString):
            vals = list(makeSet(makeList(valueString.split(','))))
            obj['processedData'][obj['propUri']] = vals
        print("csvpro ",json.dumps(dumpable_obj(obj),indent=4)) 
        obj['prop']['calcValue'] = True
        return obj
    elif mode == "load":
        return ", ".join(obj.get("dataValue"))    
    return obj
    
def email_verification_processor(obj, mode="save"):
    ''' Application application initiates a proccess to verify the email 
        address is a valid working address.'''
    if mode == "load":
        return obj.get("dataValue")
    return obj

def save_file_to_repository(data,repoItemAddress):
    object_value = ""
    if repoItemAddress:
        print("~~~~~~~~ write code here")
    else:
        repository_result = requests.post(
                    current_app.config.get("REPOSITORY_URL"),
                    data=data.read(),
    				headers={"Content-type": "'image/png'"})
        object_value = repository_result.text
    return iri(object_value)
        
def password_processor(obj, mode="save"):
    """Function handles application password actions

    Returns:
        modified passed in obj
    """
    if mode in ["save","verify"]:
        # find the salt property
        salt_url = "http://knowledgelinks.io/ns/data-resources/SaltProcessor"
        className = obj['prop'].get("className")
        classProperties = getattr(get_framework(),className).properties
        salt_property = None
        # find the property Uri that stores the salt value
        for propName, classProp in classProperties.items():
            if classProp.get("propertyProcessing") == salt_url:
                salt_property = classProp.get("propUri")
        # if in save mode create a hashed password 
        if mode == "save":
            # if the there is not a new password in the data return the obj
            if IsNotNull(obj['prop']['new']) or obj['prop']['new']!='None':
                # if a salt has not been created call the salt processor
                if not obj['processedData'].get(salt_property):
                    obj = salt_processor(obj,mode,salt_property=salt_property)
                # create the hash
                salt = obj['processedData'].get(salt_property)
                hash = sha256_crypt.encrypt(obj['prop']['new']+salt)
                # assign the hashed password to the processedData
                obj['processedData'][obj['propUri']] = hash
                obj['prop']['calcValue'] = True
            return obj
        # if in verify mode - look up the hash and return true or false
        elif mode == "verify":
            return sha256_crypt.verify(obj['password']+obj['salt'],obj['hash'])
    if mode == "load":
        return obj.get("dataValue")
    return obj
    
def salt_processor(obj, mode="save", **kwargs):
    '''Generates a random string for salting'''
    if mode == "load":
        return obj.get("dataValue")
    length = 32
    obj['prop']['calcValue'] = True
    # if called from the password processor the kwargs will have a 
    # salt_property and we can automatically generate a new one
    if kwargs.get('salt_property'):
        obj['processedData'][kwargs['salt_property']] = \
                        b64encode(os.urandom(length)).decode('utf-8')
        return obj
    # if the salt already exisits in the processed data return the obj
    # the processor may have been called by the password processor
    if IsNotNull(obj['processedData'].get(obj['propUri'])):
        return obj
        
    # find the password property
    className = obj['prop'].get("className")
    classProperties = getattr(get_framework(),className).properties
    password_property = None
    for propName, classProp in classProperties.items():
        if classProp.get("propertyProcessing") == \
                "http://knowledgelinks.io/ns/data-resources/PasswordProcessor":
            password_property = obj['preSaveData'].get(\
                                            classProp.get("propUri"))
                                            
    # check if there is a new password in the preSaveData
    #                         or
    # if the salt property is required and the old salt is empty
    if IsNotNull(password_property.get('new')) or \
                                (obj['prop'].get('required') and \
                                        not IsNotNull(obj['prop']['old'])):
        obj['processedData'][obj['propUri']] = \
                    b64encode(os.urandom(length)).decode('utf-8')
        
    obj['prop']['calcValue'] = True    
    return obj
    
def calculation_processor(obj, mode="save"):
    ''' Application should proccess the property according to the rules listed 
        in the kds:calulation property.'''
        
    if mode == "save":
        calculation = obj['prop'].get('calculation')
        if calculation:
            if calculation.startswith("slugify"):
                propUri = calculation[calculation.find("(")+1:\
                                                        calculation.find(")")]
                if not propUri.startswith("http"):
                    ns = propUri[:propUri.find(":")]
                    name = propUri[propUri.find(":")+1:]
                    propUri = get_app_ns_uri(ns) + name
                valueToSlug = obj['processedData'].get(propUri,\
                                        obj['preSaveData'].get(propUri,{}\
                                            ).get('new',None))
                if IsNotNull(valueToSlug):
                    obj['processedData'][obj['propUri']] = slugify(valueToSlug)
                    obj['prop']['calcValue'] = True
            else:
                x=y
    elif mode == "load":
        return obj.get("dataValue")                
    
    return obj
    
def getWtFormField(field):
    form_field = None
    fieldLabel = field.get("formLabelName",'')
    #print("______label:", fieldLabel)
    fieldName = field.get("formFieldName",'')
    fieldTypeObj = field.get("fieldType",{})
    if isinstance(fieldTypeObj.get('type'),list):
        fieldTypeObj = fieldTypeObj['type'][0]
    fieldValidators = getWtValidators(field)
    fieldType = "kdr:" + fieldTypeObj.get('type','').replace( \
            "http://knowledgelinks.io/ns/data-resources/","")
    #print("fieldType: ",fieldType)
    if fieldType == 'kdr:TextField':
        form_field = StringField(fieldLabel, fieldValidators, description= \
                field.get('formFieldHelp',''))
    elif fieldType == 'kdr:ServerField':
        form_field = None
        #form_field = StringField(fieldLabel, fieldValidators, description= \
            #field.get('formFieldHelp',''))
    elif fieldType == 'kdr:TextAreaField':
        form_field = TextAreaField(fieldLabel, fieldValidators, description = \
                field.get('formFieldHelp',''))
    elif fieldType == 'kdr:PasswordField':
        #print("!!!! Mode: ",fieldTypeObj.get('fieldMode'))
        fieldMode = fieldTypeObj.get('fieldMode','').replace( \
                "http://knowledgelinks.io/ns/data-resources/","")
        if fieldMode == "InitialPassword":   
            form_field = [
                            {"fieldName":fieldName,"field":PasswordField( \
                                    fieldLabel, fieldValidators, \
                                    description=field.get('formFieldHelp',\
                                    ''))},
                            {"fieldName":fieldName + "_confirm", "field": \
                                    PasswordField("Re-enter"),"doNotSave":True}
                         ]
        elif fieldMode == "ChangePassword":
            form_field = [
                            {"fieldName":fieldName + "_old","field": \
                                    PasswordField("Current"),"doNotSave":True},
                            {"fieldName":fieldName,"field":\
                                    PasswordField("New")},
                            {"fieldName":fieldName + "_confirm", "field": \
                                    PasswordField("Re-enter"),"doNotSave":True}
                         ]
        elif fieldMode == "LoginPassword":
            form_field = PasswordField(fieldLabel, fieldValidators, \
                    description=field.get('formFieldHelp',''))
    elif fieldType == 'kdr:BooleanField':
        form_field = BooleanField(fieldLabel, fieldValidators, description = \
                field.get('formFieldHelp',''))
    elif fieldType == 'kdr:FileField':
        form_field = FileField(fieldLabel, fieldValidators, description = \
                field.get('formFieldHelp',''))
    elif fieldType == 'kdr:DateField':
        form_field = DateField(fieldLabel, fieldValidators, description = \
                field.get('formFieldHelp',''), format= \
            get_framework().rdf_app_dict['application'].get('dataFormats',{}\
                    ).get('pythonDateFormat',''))
    elif fieldType == 'kdr:DateTimeField':
        form_field = DateTimeField(fieldLabel, fieldValidators, description = \
                field.get('formFieldHelp',''))
    elif fieldType == 'kdr:SelectField':
        #print("--Select Field: ",fieldLabel, fieldValidators, description= \
                #field.get('formFieldHelp',''))
        form_field = SelectField(fieldLabel, fieldValidators, description = \
                field.get('formFieldHelp',''))
        #form_field = StringField(fieldLabel, fieldValidators, description= \
                #field.get('formFieldHelp',''))
    elif fieldType == 'kdr:ImageFileOrURLField':
        form_field = [
                        {"fieldName":fieldName +"_image", "field":FileField(\
                                    "Image File")},
                        {"fieldName":fieldName + "_url", "field":StringField(\
                                    "Image Url",[URL])}
                     ]
    else:
        form_field = StringField(fieldLabel, fieldValidators, description = \
                field.get('formFieldHelp',''))
    #print("--form_field: ",form_field)
    return form_field 

def getWtValidators(field):
    ''' reads the list of validators for the field and returns the wtforms 
        validator list'''
    fieldValidators = []
    if field.get('required') == True:
        fieldValidators.append(InputRequired())
    
    validatorList = makeList(field.get('validators', []))
    for v in validatorList:
        vType = v['type'].replace(\
                "http://knowledgelinks.io/ns/data-resources/","kdr:")
        if vType == 'kdr:PasswordValidator':
            fieldValidators.append(
                EqualTo(
                    field.get("formFieldName", '') +'_confirm', 
                    message='Passwords must match'))
        if vType == 'kdr:EmailValidator':
            fieldValidators.append(Email(message=\
                    'Enter a valid email address'))
        if vType ==  'kdr:UrlValidator':
            fieldValidators.append(URL(message=\
                    'Enter a valid URL/web address'))
        if vType ==  'kdr:UniqueValueValidator':
            x=0
            #fieldValidators.append(UniqueDatabaseCheck(message=\
                    #'The Value enter is already exists'))
           #print("need to create uniquevalue validator")
        if vType ==  'kdr:StringLengthValidator':
            p = v.get('parameters')
            p1 = p.split(',')
            pObj={}
            for param in p1:
                nParam = param.split('=')
                pObj[nParam[0]]=nParam[1]
            field_min = int(pObj.get('min', 0))
            field_max = int(pObj.get('max',1028))
            fieldValidators.append(Length(
                min=field_min,
                max=field_max,
                message="{} size must be between {} and {} characters".format(
                    field.get("formFieldName"),
                    field_min, 
                    field_max)))
    return fieldValidators
      
def getFieldJson (field,instructions,instance,userInfo,itemPermissions=[]):
    '''This function will read through the RDF defined info and proccess the
	json to retrun the correct values for the instance, security and details'''
    rdfApp = get_framework().rdf_app_dict['application']
    instance = instance.replace(".html","")
    # Determine Security Access
    nField={}
    accessLevel = getFieldSecurityAccess(field,userInfo,itemPermissions)
    if "Read" not in accessLevel:
        return None
    nField['accessLevel'] = accessLevel

    # get form instance info 
    formInstanceInfo = {}
    formFieldInstanceTypeList = makeList(field.get('formInstance',field.get(\
            'formDefault',{}).get('formInstance',[])))
    for f in formFieldInstanceTypeList:
        if f.get('formInstanceType') == instance:
            formInstanceInfo = f

    # Determine the field paramaters
    nField['formFieldName'] = formInstanceInfo.get('formFieldName',field.get(\
            "formFieldName",field.get('formDefault',{}).get(\
            'formFieldName',"")))
    #if nField['formFieldName'] == 'password':
    #    x=y
    nField['fieldType'] = formInstanceInfo.get('fieldType',field.get(\
            'fieldType',field.get('formDefault',{}).get('fieldType',"")))
    #print("fieldType Type: ",nField['formFieldName']," - ",\
            #nField['fieldType'])
    if not isinstance(nField['fieldType'],dict):
        nField['fieldType'] = {"type":nField['fieldType']}
    
    nField['formLabelName'] = formInstanceInfo.get('formlabelName',\
            field.get("formLabelName",field.get('formDefault',{}).get(\
            'formLabelName',"")))
    nField['formFieldHelp'] = formInstanceInfo.get('formFieldHelp',\
            field.get("formFieldHelp",field.get('formDefault',{}).get(\
            'formFieldHelp',"")))
    nField['formFieldOrder'] = formInstanceInfo.get('formFieldOrder',\
            field.get("formFieldOrder",field.get('formDefault',{}).get(\
            'formFieldOrder',"")))
    nField['formLayoutRow'] = formInstanceInfo.get('formLayoutRow',\
            field.get("formLayoutRow",field.get('formDefault',{}).get(\
            'formLayoutRow',"")))
    nField['propUri'] = field.get('propUri')
    nField['className'] = field.get('className')
    nField['classUri'] = field.get('classUri')
    
    # get applicationActionList 
    nField['actionList'] = makeSet(formInstanceInfo.get(\
            'applicationAction',set()))
    nField['actionList'].union(makeSet(field.get('applicationAction',set())))
    nField['actionList'] = list(nField['actionList'])
    # get valiator list
    nField['validators'] = makeList(formInstanceInfo.get('formValidation',[]))
    nField['validators'] += makeList(field.get('formValidation',[]))
    nField['validators'] += makeList(field.get('propertyValidation',[]))    
    
    # get processing list
    nField['processors'] = makeList(formInstanceInfo.get('formProcessing',[]))
    nField['processors'] += makeList(field.get('formProcessing',[]))
    nField['processors'] += makeList(field.get('propertyProcessing',[]))
        
    # get required state
    required = False
    if (field.get('propUri') in makeList(field.get('classInfo',{}).get(\
            'primaryKey',[]))) or (field.get('requiredField',False)) :
        required = True
    if field.get('classUri') in makeList(field.get('requiredByDomain',{})):
        required= True
    nField['required'] = required
    
    # Determine EditState
    if ("Write" in accessLevel) and (\
            "http://knowledgelinks.io/ns/data-resources/NotEditable" \
            not in nField['actionList']):
        nField['editable'] = True
    else:
        nField['editable'] = False
        
    # Determine css classes
    css = formInstanceInfo.get('overideCss',field.get('overideCss',\
            instructions.get('overideCss',None)))
    if css is None:
        css = rdfApp.get('formDefault',{}).get('fieldCss','')
        css = css.strip() + " " + instructions.get('propertyAddOnCss','')
        css = css.strip() + " " + formInstanceInfo.get('addOnCss',field.get(\
                'addOnCss',field.get('formDefault',{}).get('addOnCss','')))
        css = css.strip()
    nField['css'] = css
    
    return nField

def getFormInstructionJson (instructions,instance):
    ''' This function will read through the RDF defined info and proccess the 
        json to retrun the correct instructions for the specified form
        instance.'''
    
    rdfApp = get_framework().rdf_app_dict['application']
    #print("inst------",instructions) 
# get form instance info 
    formInstanceInfo = {}
    formInstanceTypeList = makeList(instructions.get('formInstance',[]))
    for f in formInstanceTypeList:
        if f.get('formInstanceType') == instance:
            formInstanceInfo = f
    nInstr = {}
    #print("------",formInstanceInfo)    
#Determine the form paramaters
    nInstr['formTitle'] = formInstanceInfo.get('formTitle',\
            instructions.get("formTitle",""))
    nInstr['formDescription'] = formInstanceInfo.get('formDescription',\
            instructions.get("formDescription",""))
    nInstr['form_Method'] = formInstanceInfo.get('form_Method',\
            instructions.get("form_Method",""))
    nInstr['form_enctype'] = formInstanceInfo.get('form_enctype',\
            instructions.get("form_enctype",""))
    nInstr['propertyAddOnCss'] = formInstanceInfo.get('propertyAddOnCss',\
            instructions.get("propertyAddOnCss",""))
    nInstr['lookupClassUri'] = formInstanceInfo.get('lookupClassUri',\
            instructions.get("lookupClassUri",""))  
    nInstr['lookupPropertyUri'] = formInstanceInfo.get('lookupPropertyUri',\
            instructions.get("lookupPropertyUri",""))
    nInstr['submitSuccessRedirect'] = \
            formInstanceInfo.get('submitSuccessRedirect',
                    instructions.get("submitSuccessRedirect",""))
    nInstr['submitFailRedirect'] = \
            formInstanceInfo.get('submitFailRedirect',
                    instructions.get("submitFailRedirect",""))

# Determine css classes
    #form row css 
    css = formInstanceInfo.get('rowOverideCss',instructions.get(\
            'rowOverideCss',None))
    if css is None:
        css = rdfApp.get('formDefault',{}).get('rowCss','')
        css = css.strip() + " " + formInstanceInfo.get('rowAddOnCss',\
                instructions.get('rowAddOnCss',''))
        css = css.strip() 
        css.strip()
    nInstr['rowCss'] = css
    
    #form general css
    css = formInstanceInfo.get('formOverideCss',instructions.get(\
            'formOverideCss',None))
    if css is None:
        css = rdfApp.get('formDefault',{}).get('formCss','')
        css = css.strip() + " " + formInstanceInfo.get('formAddOnCss',\
                instructions.get('formAddOnCss',''))
        css = css.strip() 
        css.strip()
    nInstr['formCss'] = css
    
    return nInstr
    
def getFieldSecurityAccess(field,userInfo,itemPermissions=[]): 
    '''This function will return level security access allowed for the field'''
    #Check application wide access
    appSecurity = userInfo.get('applicationSecurity',set())
    #Check class access
    classAccessList = makeList(field.get('classInfo',{"classSecurity":[]}\
                ).get("classSecurity",[]))
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
        
               
def rdf_framework_form_factory(name,instance='',**kwargs):
    ''' Generates a form class based on the form definitions in the 
        kds-app.ttl file
    
    keyword Args:
        classUri: the classUri used for a form with loaded data
                   ***** has to be the class of the subjectUri for 
                         the form data lookup
        subjectUri: the uri of the object that you want to lookup
    '''
    rdf_form = type(name, (Form, ), {})
    appForm = get_framework().rdf_form_dict.get(name,{})
    fields = appForm.get('properties')
    instructions = getFormInstructionJson(appForm.get('formInstructions'),\
            instance)
    lookupClassUri = kwargs.get("classUri",instructions.get("lookupClassUri"))
    lookupSubjectUri = kwargs.get("subjectUri")
    
    # get the number of rows in the form and define the fieldList as a 
    # mulit-demensional list
    fieldList = []
    formRows = int(fields[len(fields)-1].get('formLayoutRow',1))
    for i in range(0,formRows):
        fieldList.append([])
        
    '''************************** Testing Variable *************************'''
    userInfo = {
        "userGroups":[\
                    "http://knowledgelinks.io/ns/data-resources/SysAdmin-SG"],
        'applicationSecurity':["Read","Write"]
    }
    '''*********************************************************************'''
    for fld in fields:
        field = getFieldJson (fld,instructions,instance,userInfo)
        if field:
            formRow = int(field.get('formLayoutRow',1))-1
            form_field = getWtFormField(field)
            if isinstance(form_field, list):
                i=0
                #print("____----")
                for fld in form_field:
                    #print(fld)
                    if fld.get('field'):
                        nField = dict.copy(field)
                        nField['formFieldName'] = fld['fieldName']
                        nField['formFieldOrder'] = float(nField['formFieldOrder']) + i
                        if fld.get("doNotSave"):
                            nField['doNotSave'] = True
                        fieldList[formRow].append(nField)
                        #print("--Nfield: ",nField)
                        setattr(rdf_form, fld['fieldName'], fld['field'])
                        i += .1
            else:
                #print(field['formFieldName']," - ",form_field)
                if form_field:
                    #print("set --- ",field)
                    fieldList[formRow].append(field)
                    setattr(rdf_form, field['formFieldName'], form_field)
    setattr(rdf_form, 'rdfFormInfo', appForm)
    setattr(rdf_form, "rdfInstructions", instructions)
    setattr(rdf_form, "rdfFieldList", list.copy(fieldList))
    setattr(rdf_form, "rdfInstance", instance)
    setattr(rdf_form, "dataClassUri", lookupClassUri)
    setattr(rdf_form, "dataSubjectUri", lookupSubjectUri)    
    return rdf_form
    #return rdf_form
    
def makeList(value):
    ''' Takes a value and turns it into a list if it is not one
    
    !!!!! This is important becouse list(value) if perfomed on an 
    dictionary will return the keys of the dictionary in a list and not
    the dictionay as an element in the list. i.e.
        x = {"first":1,"second":2}
        list(x) = ["first","second"]
        makeList(x) =[{"first":1,"second":2}]
    '''    
    if not isinstance(value, list):
        value = [value]
    return value
    
def makeSet(value):
    ''' Takes a value and turns it into a set
    
    !!!! This is important because set(string) will parse a string to 
    individual characters vs. adding the string as an element of 
    the set i.e.
        x = 'setvalue'
        set(x) = {'t', 'a', 'e', 'v', 'u', 's', 'l'}
        makeSet(x) = {'setvalue'}
    '''
    returnSet = set()
    if isinstance(value, list):
        for i in value:
            returnSet.add(i)
    elif isinstance(value, set):
        returnSet = value
    else:
        returnSet.add(value)
    return returnSet
    
def get_framework(reset=False):
    global rdf
    if reset:
        rdf = RdfFramework()
    else:
        try:
            test = rdf
        except:
            rdf = RdfFramework()
    return rdf
    
def query_select_options(field):
    prefix = get_framework().getPrefix()
    selectQuery = field.get('fieldType',{}).get('selectQuery',None)
    selectList = {}
    options = []
    if selectQuery:
        print(prefix+selectQuery)
        code_timer().log("formTest","----Sending query to triplestore")
        selectList =  requests.post( 
            current_app.config.get('TRIPLESTORE_URL'),
            data={"query": prefix + selectQuery,
                  "format": "json"})
        code_timer().log("formTest","----Recieved query from triplestore")
        rawOptions = selectList.json().get('results',{}).get('bindings',[])
        boundVar = field.get('fieldType',{}).get('selectBoundValue',''\
                ).replace("?","")
        displayVar = field.get('fieldType',{}).get('selectDisplay',''\
                ).replace("?","")
        for row in rawOptions:
            options.append(
                {
                    "id":iri(row.get(boundVar,{}).get('value','')),
                    "value":row.get(displayVar,{}).get('value','')
                })
    return options
    
def load_form_select_options(rdfForm,basepath=""):
    ''' queries the triplestore for the select options
    
    !!!!!!!!!!!!!! based on performace this needs to be sent to the 
    triplestore as one query. Each query to the triplestore is a minimum
    1000+ ms !!!!!!!'''
    
    for row in rdfForm.rdfFieldList:
        for fld in row:
            if fld.get('fieldType',{}).get('type',"") == \
                    'http://knowledgelinks.io/ns/data-resources/SelectField':
                options = query_select_options(fld)
                #print("oooooooo\n",options)
                fldName = fld.get('formFieldName',None)
                _wt_field = getattr(rdfForm,fldName)
                _wt_field.choices = [(o['id'], o['value']) \
                        for o in options]
                # add an attribute for the displayform with the displayed
                # element name
                if IsNotNull(_wt_field.data):
                    for o in options:
                        if o['id'] == _wt_field.data:
                            formName = get_framework().getFormName(\
                                    fld.get("fieldType",{}).get("linkedForm"))
                            if IsNotNull(formName):
                                _data = "{}'{}{}/{}.{}{}'>{}</a>".format(
                                        "<a href=",
                                        basepath,
                                        formName,
                                        "DisplayForm",
                                        "html?id=",
                                        re.sub(r"[<>]","",o['id']),
                                        o['value'])
                            else:
                                _data = o['value']
                                        
                            _wt_field.selectDisplay = _data
                        break 
                    
    return rdfForm
    
def makeTriple (sub,pred,obj):
    """Takes a subject predicate and object and joins them with a space 
	in between

    Args:
        sub -- Subject
        pred -- Predicate
        obj  -- Object
    Returns
        str
	"""
    return "{s} {p} {o} .".format(s=sub, p=pred, o=obj)
    
def xsdToPython (value, dataType, rdfType="literal"):
    ''' This will take a value and xsd datatype and convert it to a python 
        variable'''
    if dataType:
        dataType = dataType.replace(str(XSD),"xsd:")
    if not value:
        return value
    elif rdfType == "uri":
        return iri(value)
    elif not IsNotNull(value):
        return value
    elif dataType == "xsd:anyURI":
        ''' URI (Uniform Resource Identifier)'''
        return value
    elif dataType =="xsd:base64Binary":
        ''' Binary content coded as "base64"'''
        return value.decode()
    elif dataType =="xsd:boolean":
        ''' Boolean (true or false)'''
        if IsNotNull(value):
            if lower(value) in ['true', '1', 't', 'y', 'yes', 'yeah', 'yup', \
                    'certainly', 'uh-huh']:
                return True
            elif lower(value) in ['false', '0', 'n', 'no']:
                return False
            else:
                return None
        else:
            return None
    elif dataType =="xsd:byte":
        ''' Signed value of 8 bits'''
        return value.decode()
    elif dataType =="xsd:date":
        ''' Gregorian calendar date'''
        tempValue = parse(value)
        dateFormat = get_framework().rdf_app_dict['application'].get(\
                'dataFormats',{}).get('pythonDateFormat','')
        return tempValue.strftime(dateFormat)
    elif dataType =="xsd:dateTime":
        ''' Instant of time (Gregorian calendar)'''
        return parse(value)
    elif dataType =="xsd:decimal":
        ''' Decimal numbers'''
        return float(value)
    elif dataType =="xsd:double":
        ''' IEEE 64'''
        return float(value)
    elif dataType =="xsd:duration":
        ''' Time durations'''
        return timedelta(milleseconds=float(value))
    elif dataType =="xsd:ENTITIES":
        ''' Whitespace'''
        return value
    elif dataType =="xsd:ENTITY":
        ''' Reference to an unparsed entity'''
        return value
    elif dataType =="xsd:float":
        ''' IEEE 32'''
        return float(value)
    elif dataType =="xsd:gDay":
        ''' Recurring period of time: monthly day'''
        return value
    elif dataType =="xsd:gMonth":
        ''' Recurring period of time: yearly month'''
        return value
    elif dataType =="xsd:gMonthDay":
        ''' Recurring period of time: yearly day'''
        return value
    elif dataType =="xsd:gYear":
        ''' Period of one year'''
        return value
    elif dataType =="xsd:gYearMonth":
        ''' Period of one month'''
        return value
    elif dataType =="xsd:hexBinary":
        ''' Binary contents coded in hexadecimal'''
        return value
    elif dataType =="xsd:ID":
        ''' Definition of unique identifiers'''
        return value
    elif dataType =="xsd:IDREF":
        ''' Definition of references to unique identifiers'''
        return value
    elif dataType =="xsd:IDREFS":
        ''' Definition of lists of references to unique identifiers'''
        return value
    elif dataType =="xsd:int":
        '''32'''
        return value
    elif dataType =="xsd:integer":
        ''' Signed integers of arbitrary length'''
        return int(value)
    elif dataType =="xsd:language":
        ''' RFC 1766 language codes'''
        return value
    elif dataType =="xsd:long":
        '''64'''
        return int(value)
    elif dataType =="xsd:Name":
        ''' XML 1.O name'''
        return value
    elif dataType =="xsd:NCName":
        ''' Unqualified names'''
        return value
    elif dataType =="xsd:negativeInteger":
        ''' Strictly negative integers of arbitrary length'''
        return abs(int(value))*-1
    elif dataType =="xsd:NMTOKEN":
        ''' XML 1.0 name token (NMTOKEN)'''
        return value
    elif dataType =="xsd:NMTOKENS":
        ''' List of XML 1.0 name tokens (NMTOKEN)'''
        return value
    elif dataType =="xsd:nonNegativeInteger":
        ''' Integers of arbitrary length positive or equal to zero'''
        return abs(int(value))
    elif dataType =="xsd:nonPositiveInteger":
        ''' Integers of arbitrary length negative or equal to zero'''
        return abs(int(value))*-1
    elif dataType =="xsd:normalizedString":
        ''' Whitespace'''
        return value
    elif dataType =="xsd:NOTATION":
        ''' Emulation of the XML 1.0 feature'''
        return value
    elif dataType =="xsd:positiveInteger":
        ''' Strictly positive integers of arbitrary length'''
        return abs(int(value))
    elif dataType =="xsd:QName":
        ''' Namespaces in XML'''
        return value
    elif dataType =="xsd:short":
        '''32'''
        return value
    elif dataType =="xsd:string":
        ''' Any string'''
        return value
    elif dataType =="xsd:time":
        ''' Point in time recurring each day'''
        return parse(value)
    elif dataType =="xsd:token":
        ''' Whitespace'''
        return value
    elif dataType =="xsd:unsignedByte":
        ''' Unsigned value of 8 bits'''
        return value.decode()
    elif dataType =="xsd:unsignedInt":
        ''' Unsigned integer of 32 bits'''
        return int(value)
    elif dataType =="xsd:unsignedLong":
        ''' Unsigned integer of 64 bits'''
        return int(value)
    elif dataType =="xsd:unsignedShort":
        ''' Unsigned integer of 16 bits'''
        return int(value)
    else:
        return value
        
def convertSPOtoDict(data,mode="subject"):
    '''Takes the SPAQRL query results and converts them to a python Dict
    
    mode: subject --> groups based on subject
    '''
    returnObj = {}
    if mode == "subject":
        for item in data:
            if returnObj.get(item['s']['value']):
                if returnObj[item['s']['value']].get(item['p']['value']):
                    objList = makeList(\
                            returnObj[item['s']['value']][item['p']['value']])
                    objList.append(xsdToPython (item['o']['value'], \
                            item['o'].get("datatype"), item['o']['type']))
                    returnObj[item['s']['value']][item['p']['value']] = objList
                else:
                    returnObj[item['s']['value']][item['p']['value']] = \
                        xsdToPython (item['o']['value'], item['o'].get(\
                                "datatype"), item['o']['type'])
            else:
                returnObj[item['s']['value']] = {}
                returnObj[item['s']['value']][item['p']['value']] = \
                        xsdToPython (item['o']['value'], item['o'].get(\
                        "datatype"), item['o']['type'])
        return returnObj

class CodeTimer(object):
    '''simple class for placing timers in the code for performance testing'''
    
    def addTimer(self,timer_name):
        setattr(self,timer_name,[])
    def log(self,timer_name,node):
        timestamp = time.time()
        if hasattr(self,timer_name):
            getattr(self,timer_name).append({
                    "node":node,
                    "time":timestamp})
        else:
            setattr(self,timer_name,[{"node":node,"time":timestamp}])
    def printTimer(self, timer_name, **kwargs):
        delete_timer = kwargs.get("delete",False)
        print("|-------- {} [Time Log Calculation]-----------------|".format(\
                timer_name))
        print("StartDiff\tLastNodeDiff\tNodeName")
        time_log = getattr(self,timer_name)
        start_time = time_log[0]['time']
        previous_time = start_time
        for entry in time_log:
            time_diff = (entry['time'] - previous_time)  *1000
            time_from_start = (entry['time'] - start_time) *1000
            previous_time = entry['time']
            print("{:.1f}\t\t{:.1f}\t\t{}".format(time_from_start,
                                                  time_diff,
                                                  entry['node']))
        print("|------------------------------------------------------------|")
        if delete_timer:
            self.deleteTimer(timer_name)
            
    def deleteTimer(self, timer_name):
        if hasattr(self,timer_name):
            delattr(self,timer_name)
        
def code_timer(reset=False):
    '''Sets a global variable for tracking the timer accross multiple
    files '''
    
    global codeTimer
    if reset:
        codeTimer = CodeTimer()
    else:
        try:
            test = codeTimer
        except:
            codeTimer = CodeTimer()
    return codeTimer
                
    
def calculate_time_log(time_log):
    start_time = time_log[0]['time']
    previous_time = start_time
    print("|------------------Time Log Calculation--------------------------|")
    print("StartDiff\tLastNodeDiff\tNodeName")
    for entry in time_log:
        time_diff = (entry['time'] - previous_time) *1000
        time_from_start = (entry['time'] - start_time) *1000
        previous_time = entry['time']
        print("{:.1f}\t\t{:.1f}\t\t{}".format(time_from_start,
                                              time_diff,
                                              entry['node']))
    print("|----------------------------------------------------------------|")
       
      
def dumpable_obj(obj):
    ''' takes an object that fails with json.dumps and converts it to
    a json.dumps dumpable object. This is useful for debuging code when
    you want to dump an object for easy reading'''
    
    if isinstance(obj,list):
        returnList = []
        for item in obj:
            if isinstance(item,list):
                returnList.append(dumpable_obj(item))
            elif isinstance(item,set):
                returnList.append(list(item))
            elif isinstance(item,dict):
                returnList.append(dumpable_obj(item))
            else:
                try:
                    x=json.dumps(item)
                    returnList.append(item)
                except:
                    returnList.append(str(type(item)))
        return returnList
    elif isinstance(obj,set):
        return(list(obj))
    elif isinstance(obj,dict):
        returnObj = {}
        for key,item in obj.items():
            if isinstance(item,list):
                returnObj[key] = dumpable_obj(item)
            elif isinstance(item,set):
                returnObj[key] = list(item)
            elif isinstance(item,dict):
                returnObj[key] = dumpable_obj(item)
            else: 
                try:
                    x = json.dumps(item)
                    returnObj[key] = item
                except:
                    returnObj[key] = str(type(item))
        return returnObj
    else:
        try:
            x = json.dumps(item)
            print("test")
            return item
        except:
            print ("except")
            return str(type(item))
   
def remove_null(obj):
    ''' reads through a list or set and strips any null values'''
    if isinstance(obj,set):
        try:
            obj.remove(None)
        except:
            pass
    elif isinstance(obj,list):
        for item in Obj:
            if not IsNotNull(item):
                obj.remove(item)
    return obj
                
class DeleteProperty(object):
    ''' dummy class for tagging items to be deleted. This will prevent
    passed in data ever being confused with marking a property for 
    deletion. '''
    def __init__(self):
        setattr(self,"delete",True)
        
class NotInFormClass(object):
    ''' dummy class for tagging properties that were never in a form. 
    This will prevent passed in data ever being confused with a property
    that was never in the form. '''
    def __init__(self):
        setattr(self,"notInForm",True)
        
def slugify(value):
    """Converts to lowercase, removes non-word characters (alphanumerics and
    underscores) and converts spaces to hyphens. Also strips leading and
    trailing whitespace using Django format

    Args:

    """
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)
    
def get_app_ns_uri(value):
    ''' looks in the framework for the namespace uri'''
    for ns in get_framework().rdf_app_dict['application'].get(\
                                                       "appNameSpace",[]):
        if ns.get('prefix') == value:
            return ns.get('nameSpaceUri')
            
def cleanIri(uriString):
    '''removes the <> signs from a string start and end'''
    if isinstance(uriString, str):
        if uriString[:1] == "<" and uriString[len(uriString)-1:] == ">" :
            uriString = uriString[1:len(uriString)-1]
    return uriString
    
def clean_processors(processorList,classUri=None):
        ''' some of the processors are stored as objects and need to retrun 
            them as a list of string names'''
        returnList = []
        print("processorList __ ",processorList)
        for item in processorList:
            if isinstance(item,dict):
                if classUri:
                    if item.get("appliesTo") == classUri:
                        returnList.append(item.get("propertyProcessing"))
                else:
                    returnList.append(item.get("propertyProcessing"))   
            else:
                returnList.append(item)
        return returnList
        
def get_form_redirect_url(rdfForm,state,base_url,current_url,idValue=None):
    if state == "success":
        urlInstructions = rdfForm.rdfInstructions.get("submitSuccessRedirect")
        if not urlInstructions:
            return base_url
    if state == "fail":
        urlInstructions = rdfForm.rdfInstructions.get("submitFailRedirect")
        if not urlInstructions:
            return "!--currentpage"
    if urlInstructions == "!--currentpage":
        return current_url
    elif urlInstructions == \
            "http://knowledgelinks.io/ns/data-resources/DisplayForm":
        formName = rdfForm.rdfFormInfo.get("formName")
        return "{}{}/DisplayForm.html?id={}".format(base_url,
                                                    formName,
                                                    idValue)
    elif urlInstructions == "!--homepage":
        return base_url
    else:
        return base_url
        
