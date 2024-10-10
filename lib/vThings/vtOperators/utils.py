# Utility Functions
from multipledispatch import dispatch
from collections.abc import Iterable
from pathlib import Path

import importlib
import importlib.util
import sys
import os

import json
import copy
import re

import numbers
import decimal

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, project_root)
from lib.dgal_lib import dgalPy as dgal

#-------------------------------------------------------------------------------

# instantiator
@dispatch((str,int,float))
def instantiator(input):
    ''' JSON parser function that recursively
    instantiates the virtual things.

    Parameters:
        input: an atomic value

    Returns:
        output: an atomic value
    '''
    return input

@dispatch(Iterable)
def instantiator(input):
    ''' JSON parser function that recursively
    instantiates the virtual things.

    Parameters:
        input (list): a list

    Returns:
        output (list): a list
    '''
    rsList = [instantiator(item) for item in input]
    return rsList

#-------------------------------------------------------------------------------

# helper functions to convert shortcuts into full path
# according to ref in context and instantiate partial VT
def refConvertor(input):
    # wrapper function for refConvert
    # convert deep copy of the input,
    # instantiate the vt and return the new copy
    inputCopy = copy.deepcopy(input)
    if "@context" in inputCopy:
        con = input["@context"]
    else:
        con = {}
    refConvert(inputCopy, con)
    return inputCopy

def isRef(dict):
    # assume input is a dict
    if "@ref" in dict:
        if len(dict) == 1:
            return True
        else:
            raise Exception("ref dict is invalid!")
    else:
        return False

def fullPath(shortcut, context={}):
    shortPath = shortcut.split('/')[0]
    spLen = len(shortPath)
    dir = context[shortPath]
    v1 = shortcut[spLen+1:]
    fullPath = dir + v1
    return fullPath

def extractFileDict(dict, context):
    k = next(iter(dict))  # Get the first (and only) key in the dictionary
    dir = dict[k]
    dir = fullPath(dir, context)
    #do not modify original object
    dir = project_root + '/' + dir
    file = dir + ".json"
    with open(file, 'r') as f:
        data = json.load(f)
    return data

def refConvert(input, context):
    ''' converts ref with @xxx into full path
    Assumes:
        - input may have a context
        - references has @ in the value field

    Parameters:
        input (dict): a dict

    Modifies:
        input
    '''

    # base case, no ref or no recurse
    if not isinstance(input, (dict, list)):
        return
    elif isinstance(input, list):
        # output = [refConvertor(l, con) for l in input]
        # return output
        for l in input:
            refConvert(l, context)
    elif isinstance(input, dict):
        for k,v in input.items():
            if not isinstance(v, (dict, list)):
                pass
            elif isinstance(v, dict) and isRef(v):
                fileDict = extractFileDict(v, context) # return ref dict extracted from the file
                out = refConvertor(fileDict)
                input[k] = out[k]
            else:
                refConvert(v, context)
    else:
        raise Exception("Invalid input structure!")

# integrated in refConvertor
@dispatch(dict)
def instantiator(input):
    ''' JSON parser function that recursively
    instantiates the virtual things.

    Parameters:
        input (dict): a dict

    Returns:
        output (dict): a dict
    '''

    rsDict = {}

    for k,v in input.items():
        if type(v)==dict:
            refConvertor(v)
            rsDict[k] = instantiator(v)
        elif type(v)==list:
            refConvertor(v)
            rsDict[k] = instantiator(v)
        elif type(v)==str:
            if "@ref" in k:
                # a sub key in v is @ref
                print(f"@ref in {k}, path {v}")
                dir = input[k]
                #do not modify original object
                dir = project_root + '/' + dir
                print("dir get: "+dir)
                file = dir + ".json"
                with open(file, 'r') as f:
                    data = json.load(f)
                refConvertor(data)
                rsDict[k] = instantiator(data)
            else:
                rsDict[k] = instantiator(v)
        else:
            rsDict[k] = instantiator(v)
    return rsDict

# isFlowRef helper function in dev
#def isFlowRef(input):
    # Returns true if input is Dict originating
    # from JSON object, every key is string
    # false otherwise

def flowRefConvertor(input):
    # converts flow ref with @productRef
    # into full version of ref which is the product id
    rsDict = copy.deepcopy(input)
    for k,v in input.items():
        if k == "flows" and type(v)==dict:
            #print("flow ref convert")
            for k1,v1 in v.items():
                if "@productRef" in v1:
                    #print("@productRef convert")
                    if "@context" in input:
                        #print("@context convert")
                        dir = input["@context"]["@productRef"]
                        v1 = v1[12:]
                        p1 = v1.split('/')[-1]
                        v1 = dir + v1 + '/' + p1
                        k1 = v1 + '/' + p1
                        #print(k1)
                        #print(v1)
                        rsDict["products"][k1]={"@ref": v1}
                    else:
                        raise Exception("@context not specified!")
    return rsDict

def prodRefConvertor(input):
    # converts prod ref with @productRef
    # into full version of ref which is the product id
    rsDict = copy.deepcopy(input)
    for k,v in input.items():
        if k == "components" and type(v)==dict:
            #print("flow ref convert")
            for k1,v1 in v.items():
                if "@productRef" in v1["params"]["@ref"]:
                    #print("@productRef convert")
                    #print("k1 "+str(k1)+" v1 "+str(v1))
                    if "@context" in input:
                        #print("@context convert")
                        dir = input["@context"]["@productRef"]
                        v1["params"]["@ref"] = v1["params"]["@ref"][12:]
                        p1 = v1["params"]["@ref"].split('/')[-1]
                        rsDict["components"][k1]["params"]["@ref"] = dir + v1["params"]["@ref"] + '/' + p1
                        #k1 = v1["ref"] + '/' + p1
                        #print(k1)
                        #print(v1)
                        #rsDict["products"][k1]={"@ref": v1}
                    else:
                        raise Exception("@context not specified!")
    return rsDict

# helper function to get data though key and index path
# if value not numeric, return None
# if path invalid, return None
# if undetermined value/path, return None

# original copy
# def getValueByPath(data, path):
#     if isinstance(data, (dict,list)):
#         return getValueByPath(data[path[0]], path[1:]) if path else data
#     else:
#         return data

# enhanced version that handles exceptions and returns None
def getValueByPath(data, path):
    # if data empty, return None
    #print(str(data)+" data at: "+str(path))
    # 0 counts as false in Python list
    if data==[]:
        #print(str(data)+" is empty")
        return None
    # if data None, return None
    if data is None:
        #print(str(data)+" is None")
        return None

    # check if data recursive structure
    if isinstance(data, (dict,list)):
        # if so and path exists, recursively apply function
        if path:
            try:
                return getValueByPath(data[path[0]], path[1:])
            except:
                print("Value Key or Index Warning at: "+str(path)+ " in "+ str(data))
                return data[path[0]]
                #return None
        # else atomic value, return data if number
        elif isinstance(data, numbers.Number):
            #print(str(data)+" is number")
            return data
        # return None for non-numeric data
        else:
            print(str(data)+" is not number")
            return None
    # non recursive structure, return data if number, else None
    else:
        if isinstance(data, numbers.Number):
            return data
        else:
            print(str(data)+" is not number")
            return data
            #return None



# helper function to set data though key and index path
def setValueByPath(data, path, value):
    if path and isinstance(data[path[0]], (dict,list)):
        setValueByPath(data[path[0]], path[1:], value)
    else:
        data[path[0]] = value
    return data


# helper function to recursively traverse structure, generate paths to values
def pathGenerator(d, currentPath, pathList):
    # if d is dict
    if isinstance(d, dict):
        for k,v in d.items():
            p = copy.deepcopy(currentPath)
            # if v is a dict or list, append key and iterate
            if isinstance(v, (dict, list)):
                p.append(k)
                print ("p: ",str(p))
                pathGenerator(v, p, pathList)
            # else v is data, append key to p
            else:
                p.append(k)
                # after each loop finishes by reaching data,
                # append data path to pathList
                pathList.append(p)
            print ("pathList: ",str(pathList))
    elif isinstance(d, list):
        for i in range(len(d)):
            p = copy.deepcopy(currentPath)
            # if v is a dict or list, append key and iterate
            if isinstance(d[i], (dict, list)):
                p.append(i)
                print ("p: ",str(p))
                pathGenerator(d[i], p, pathList)
            # else v is data, append key to p
            else:
                p.append(i)
                # after each loop finishes by reaching data,
                # append data path to pathList
                pathList.append(p)
            print ("pathList: ",str(pathList))
    else:
        return pathList
    return pathList




#def listAdd(list):
    # if any element is None, update structure value as None

    # else, the value is the sum of all elements in the list

    # otherwise raise exception

# recursive aggregator
def aggregator(metricSchema, metricList):
    # aggr = copy.deepcopy(metricSchema)
    # path = []
    # recAggr(path, aggr, metricList)

    ''' aggregation function that recursively aggregates the values of
    the fields for metric schemata of VS AM.

    Parameters:
        metricSchema (dict): a JSON compatible dict of the metric schema
        metricList (list): a python list of the metric schemata

    Throws:
        exception if schema is invalid

    Returns:
        output (dict): a dict of the aggregated metrics
    '''

    # schema by example/template
    # create deep copy of metricSchema as intermediate result
    # recursively traverse through metricSchema,
    # if dict, traverse using keys; if list, traverse using index
    # if (atomic value) null, remember path
    # access value of same path in metricList
    # if exist value, add value
    # if value not exist or null, set null
    # construct a list for every element
    # if all values exist, add up the values
    # if exist null, result is set to null

    # use metricSchema to generate paths?
    metricDict = copy.deepcopy(metricSchema)
    rsDict = copy.deepcopy(metricSchema)

    print("metricDict: "+ json.dumps(metricDict) + "\n")

    pathList = []
    currentPath = []
    # traverse metricDict to locate all expected null values
    pathGenerator(metricDict, currentPath, pathList)

    # loop through pathList to search for value in each metric structure
    for p in pathList:
        newMetricList = []
        # access values in metricList and generate new lists of metrics
        for m in metricList:
            # if metric value exists in metricList, append to list
            value = getValueByPath(m, p)
            newMetricList.append(value)
            #print("getValue: "+str(value)+" at "+str(p))
        # if exists missing value, append None to rsList
        if None in newMetricList:
            setValueByPath(rsDict, p, None)
            #print("rsDict append None"+" at "+str(p))
            #print(*rsDict)
        else:
            value = sum(newMetricList)
            setValueByPath(rsDict, p, value)
            #print("rsDict append: "+str(value)+" at "+str(p))
            #print(*rsDict)

    return rsDict

# helper function getModelRef
def getModelRef(input):
    # converts model ref with shortcuts into full version of ref path if needed
    # rsDict = copy.deepcopy(input)
    # iterate input items, find model
    if "model" not in input:
        raise Exception("model path not specified!")
    else:
        #print("model ref convert")
        v1 = input.get("model")
        modelRef = v1
        if v1.startswith("@"):
            sc = v1[:9]
            if "@context" in input:
                #print("@context convert")
                dir = input["@context"][sc]
                #print("dir: "+dir)
                v1 = v1[10:]
                #p1 = v1.split('/')[-1]
                v1 = dir + '/' + v1
                #print("v1: "+v1)
                modelRef = v1 + '/' + 'am.py'
                #rsDict["products"][k1]={"@ref": v1}
            else:
                raise Exception("@context not specified!")
    return modelRef

def specValidator(spec):
    # need to be implemented
    return True

# helper function specRefConvertor
def specRefConvertor(input):
    # converts spec ref with shortcuts into full version of ref path
    # used in metricSchema and objective function
    if not specValidator:
        raise Exception("Invalid spec structure!")

    if "parametersSchema" in input :
        #print("spec ref convert")
        v0 = input.get("parametersSchema")

        if v0.startswith("@") and "@context" in input:
            #print("@context convert")
            shortcut, psPath = v0.split("/", 1)
            dir = input["@context"][shortcut]

            #p1 = v1.split('/')[-1]
            v0 = dir + psPath
            #print("v1: "+v1)
            #specRef = v1 #+ '/' + 'am.py'
            #rsDict["products"][k1]={"@ref": v1}
            input["parametersSchema"]=v0
        else:
            raise Exception("@context not specified!")

    if "metricSchema" in input :
        #print("spec ref convert")
        v1 = input.get("metricSchema")

        if v1.startswith("@"):
            #print("@context convert")
            if "@context" in input:
                shortcut, msPath = v1.split("/", 1)
                dir = input["@context"][shortcut]

                #p1 = v1.split('/')[-1]
                v1 = dir + msPath
                #print("v1: "+v1)
                #specRef = v1 #+ '/' + 'am.py'
                #rsDict["products"][k1]={"@ref": v1}
                input["metricSchema"]=v1
            else:
                raise Exception("@context not specified!")
        else:
            pass

    if "objectives" in input:
        v2 = input.get("objectives").get("function").get("@functionRef")
        if v2.startswith("@") and "@context" in input:
            #print("@context convert")
            shortcut, osPath = v2.split("/", 1)
            dir = input["@context"][shortcut]
            v2 = v2[14:]
            #p1 = v1.split('/')[-1]
            v2 = dir + v2
            #print("v1: "+v1)
            #specRef = v2 #+ '/' + 'am.py'
            #rsDict["products"][k1]={"@ref": v1}
            input["objectives"]["function"]["@functionRef"]=v2

            # load objective function
            objFuncPath = input["objectives"]["function"]["@functionRef"]
            objFuncPath = objFuncPath.replace('/', '.')
            objFuncPath = re.sub(r'^\.+', '', objFuncPath)
            module_name, function_name = objFuncPath.rsplit('.', 1)
            function_name = function_name.split(':')[1]
            #print("function name:"+function_name)
            # Import the module dynamically
            module = importlib.import_module(module_name)
            # Get the function from the module
            objectives = getattr(module, function_name)
            input["objectives"]["function"] = objectives

    if "model" in input:
        #v1 = input.get("metricSchema")
        v3 = input.get("model").get("@functionRef")

        if v3.startswith("@") and "@context" in input:
            shortcut, modelPath = v3.split("/", 1)
            dir = input["@context"][shortcut]

            #p1 = v1.split('/')[-1]
            v3 = dir + modelPath
            #print("v1: "+v1)
            #specRef = v1 #+ '/' + 'am.py'
            #rsDict["products"][k1]={"@ref": v1}
            input["model"]=v3

            # load objective function
            amPath = input["model"]
            amPath = amPath.replace('/', '.')
            amPath = re.sub(r'^\.+', '', amPath)
            module_name, function_name = amPath.rsplit('.', 1)
            function_name = function_name.split(':')[1]
            # Import the module dynamically
            module = importlib.import_module(module_name)
            # Get the function from the module
            analyticModel = getattr(module, function_name)
            input["model"] = analyticModel
        else:
            raise Exception("@context not specified!")

    if "flows" in input:
        flows = input.get("flows")
        #print(str(flows))
        for k,v in flows.items():
            if "@reqTemplates" in v:
                v3 = v
                v3 = v3[14:]
                v3 = dir + v3
                input["flows"][k] = v3

    return True


# auxiliary functions
# given an object, check the object of dgal type
# extract corresponding constraints
# traverse the structure, recursively
# if the object is dgal type, remember the path, construct constraints
# not dgal type, traverse recusively, for every value of the key, invoke procedure
# else if a list, recusively iterate over the list, invoke on each element

# helper functions to recursively traverse structure, generate paths to dgal vars
def dgalPathGenerator(d, currentPath, pathList):
    if "dgalType" in d:
        return pathList
    # if d is dict
    if isinstance(d, dict):
        for k,v in d.items():
            p = copy.deepcopy(currentPath)
            # if v is a dict or list, append key and iterate
            if isinstance(v, (dict, list)) and "dgalType" not in v:
                p.append(k)
                #print ("p: ",str(p))
                dgalPathGenerator(v, p, pathList)
            # else v is data, append key to p
            elif isinstance(v, (dict, list)) and "dgalType" in v:
                p.append(k)
                # after each loop finishes by reaching data,
                # append data path to pathList
                pathList.append(p)
            else:
                pass
            #print ("pathList: ",str(pathList))
    elif isinstance(d, list):
        for i in range(len(d)):
            p = copy.deepcopy(currentPath)
            # if v is a dict or list, append key and iterate
            if isinstance(d[i], (dict, list)):
                p.append(i)
                #print ("p: ",str(p))
                dgalPathGenerator(d[i], p, pathList)
            # else v is data, append key to p
            else:
                pass
                # p.append(i)
                # # after each loop finishes by reaching data,
                # # append data path to pathList
                # pathList.append(p)
            #print ("pathList: ",str(pathList))
    else:
        pass

def extractConstraintsByPath(data, path):
    # if data empty, return None
    #print(str(data)+" data at: "+str(path))
    # 0 counts as false in Python list
    if data==[]:
        #print(str(data)+" is empty")
        return None
    # if data None, return None
    if data is None:
        #print(str(data)+" is None")
        return None
    # if path exists, recursively apply function
    if path:
        try:
            return extractConstraintsByPath(data[path[0]], path[1:])
        except:
            print("Const Key or Index Error at: "+str(path) + " in "+ str(data))
            return None
    # else atomic value, no constraint
    elif isinstance(data, dict):
        # constraint found
        return data
    # else atomic value, no constraint
    elif isinstance(data, numbers.Number):
        #print(str(data)+" is number")
        raise Exception("No bound found!")
    # return None for non-numeric data
    else:
        print(str(data)+" is not valid path!")
        return None

# metricSchema validator
def metricSchemaValidator(ms):
    # need to implement?
    return True

# extract metricSchema constraints in a dict
def metricSchemaConstraintsDict(ms, rsDict={}):
    if not metricSchemaValidator(ms):
        raise Exception("Invalid metric schema!")
    for k, v in ms.items():
        if k != "@context" and k != "model" and isinstance(v, dict):
            rsDict.update({k:{}})
            for k1, v1 in v.items():
                if isinstance(v1, dict) and ("lb" in v1 or "ub" in v1):
                    rsDict[k][k1]=v1
                    print("k: "+k+", k1: "+k1)
                    print(str(rsDict))
            if "components" in v:
                for k2, v2 in v["components"].items():
                    metricSchemaConstraintsDict(v2, rsDict=rsDict)
    return rsDict

# extract metricSchema constraints from pathList
def metricSchemaConstraints(ms, o, pathList, rsDict={}):
    if not metricSchemaValidator(ms):
        raise Exception("Invalid metric schema!")
    # bounds from ms, var from output?
    constraintsList = []
    for path in pathList:
        constraint = extractConstraintsByPath(ms, path)
        result = True
        if "lb" in constraint:
            #print("m const: "+str(constraint["lb"]))
            #print("o: "+ str(o)+" path: "+str(path))
            res = (getValueByPath(o, path) >= constraint["lb"])
            print("msc res: "+str(res))
            result = dgal.all([result, res])
        if "ub" in constraint:
            res = (getValueByPath(o, path) <= constraint["ub"])
            print("msc res: "+str(res))
            result = dgal.all([result, res])

        constraintsList.append(result)
    #return dgal.all(constraintsList)
    return constraintsList

# objSchema validator
def objSchemaValidator(objSchemaAndBounds):
    # need to implement?
    return True

# extract objSchema constraints from objPathList
def objSchemaConstraints(objSchemaAndBounds, o, objPathList, rsDict={}):
    if not objSchemaValidator(objSchemaAndBounds):
        raise Exception("Invalid objective schema!")
    # bounds from ms, var from output?
    constraintsList = []
    for path in objPathList:
        constraint = extractConstraintsByPath(objSchemaAndBounds, path)
        result = True
        if "lb" in constraint:
            #print("obj const: "+str(constraint["lb"]))
            #print("o: "+ str(o)+" path: "+str(path))
            res = (getValueByPath(o, path) >= constraint["lb"])
            print("osc res: "+str(res))
            result = dgal.all([result, res])
        if "ub" in constraint:
            res = (getValueByPath(o, path) <= constraint["ub"])
            print("osc res: "+str(res))
            result = dgal.all([result, res])

        constraintsList.append(result)
    #return dgal.all(constraintsList)
    return constraintsList
