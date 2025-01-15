import re
import sys
import json
import math
import importlib
from itertools import product
import importlib.util
import os
from math import inf

# Get the project root directory (assuming it's named "OptiGuide")
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")) + "/"
#print(project_root)

# Add the project root to sys.path
sys.path.insert(0, project_root)
# Now import the modules
from lib.dgal_lib import dgalPy as dgal
from lib.optiguide_lib import paretoDB as podb
from lib.vThings.vtOperators.vtFunctions import boundConstraints

dir=project_root+'procurementDgProject/'

#-------------------------------------------------------------------------------
# Extract model from vtSpec
def extractModel(vtSpec_path):
    with open(project_root + vtSpec_path,"r") as f:
        vtSpec = json.load(f)
    model_path = vtSpec["model"]["@functionRef"].replace('/', '.')
    model_path = re.sub(r'^\.+', '', model_path)
    module_name, function_name = model_path.rsplit(':', 1)

    # Remove the '.py' from the module name if it's there
    if module_name.endswith('.py'):
        module_name = module_name[:-3]

    # Use importlib.util to load the module
    spec = importlib.util.spec_from_file_location(module_name, project_root + vtSpec["model"]["@functionRef"].split(':')[0])
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    model = getattr(module, function_name)
    return model

#-------------------------------------------------------------------------------
# Extract input from vtSpec
def extractInput(vtSpec_path):
    with open(project_root + vtSpec_path,"r") as f:
        vtSpec = json.load(f)
    input_path = vtSpec["parametersSchema"]
    with open(project_root+input_path,"r") as f:
        input = json.load(f)
    return input

#-------------------------------------------------------------------------------
# Extract metricSchema from vtSpec
def extractMetricSchema(vtSpec_path):
    with open(project_root + vtSpec_path,"r") as f:
        vtSpec = json.load(f)
    metricSchema_path = vtSpec["metricSchema"]
    with open(project_root+metricSchema_path,"r") as f:
        metricSchema = json.load(f)
    return metricSchema

#-------------------------------------------------------------------------------
# Extract objectives schema from reqSpec
def extractObjsSchema(config):
    with open(project_root+config["reqSpec"],"r") as f:
        reqSpec = json.load(f)
    objsSchema = reqSpec["objectives"]["schema"]
    return objsSchema

#-------------------------------------------------------------------------------
# Extract objectives function from reqSpec
def extractObjsFunc(config):
    with open(project_root+config["reqSpec"],"r") as f:
        reqSpec = json.load(f)
    objsFunc_path = reqSpec["objectives"]["function"]["@functionRef"].replace('/', '.')
    objsFunc_path = re.sub(r'^\.+', '', objsFunc_path)
    module_name, function_name = objsFunc_path.rsplit(':', 1)

    # Remove the '.py' from the module name if it's there
    if module_name.endswith('.py'):
        module_name = module_name[:-3]

    # Use importlib.util to load the module
    spec = importlib.util.spec_from_file_location(module_name, project_root + reqSpec["objectives"]["function"]["@functionRef"].split(':')[0])
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    objsFunc = getattr(module, function_name)
    return objsFunc

#-------------------------------------------------------------------------------
# Extract constraints function from reqSpec
def extractConstFunc(config):
    with open(project_root+config["reqSpec"],"r") as f:
        reqSpec = json.load(f)
    constFunc_path = reqSpec["constraints"]["@functionRef"].replace('/', '.')
    constFunc_path = re.sub(r'^\.+', '', constFunc_path)
    module_name, function_name = constFunc_path.rsplit(':', 1)

    # Remove the '.py' from the module name if it's there
    if module_name.endswith('.py'):
        module_name = module_name[:-3]

    # Use importlib.util to load the module
    spec = importlib.util.spec_from_file_location(module_name, project_root + reqSpec["constraints"]["@functionRef"].split(':')[0])
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    constFunc = getattr(module, function_name)
    return constFunc

#-------------------------------------------------------------------------------
# Generate a list of weight combinations for all objectives
def generateWeights(objsSchema, num_entries, e):
    weightsList=[]
    objs_except_last = list(objsSchema.keys())[:-1]
    last_obj = list(objsSchema.keys())[-1]
    delta= ((math.pi/2) - 2*e) / num_entries
    alphas= [ e+(n * delta) for n in range(num_entries+1)]
    weights = [math.sin(a) for a in alphas]

    for combination in product(weights, repeat=len(objs_except_last)):
        sum_squrs= sum([combination[i]**2 for i in range(len(combination))])
        if sum_squrs <= 1-(weights[0]**2):
            weightsDict={}
            for i, obj in enumerate(objs_except_last):
                weightsDict[obj] = combination[i]
            weightsDict[last_obj]= math.sqrt(1- sum_squrs)
            weightsList.append(weightsDict)
    return weightsList

#-------------------------------------------------------------------------------

# Compute min and max possible value for each objective
def computeMinMax(objsSchema, config):

    # extract objectives function from reqSpec
    objsFunc = extractObjsFunc(config)

    # extract constraints function from reqSpec
    constFunc = extractConstFunc(config)

    vtSpecSet_minMaxObjs = []

    vtSpecs = config["vtSpecs"]
    for vtSpec in vtSpecs:
        # extract model from vtSpec
        model = extractModel(vtSpec)

        # extract input from vtSpec
        input = extractInput(vtSpec)

        # extract metricSchema from vtSpec
        metricSchema = extractMetricSchema(vtSpec)

        def constraints(o):
            modelComputedConstraints = constFunc(o)
            vtMetricBounds = boundConstraints(metricSchema, o)
            objs = objsFunc(o)
            objsBounds = boundConstraints(objsSchema, objs)
            constraints = dgal.all([
                modelComputedConstraints,
                vtMetricBounds,
                objsBounds
            ])
            return(constraints)

        minMaxObjs = {}
        for obj in objsSchema:
            if objsSchema[obj]["minMax"]=="min": # a minimization metric
            # optimizing the objective to find its Minimum value
                optAnswer_minObj = dgal.min({
                    "model": model,
                    "input": input,
                    "obj": lambda o: objsFunc(o)[obj],
                    "constraints": constraints,
                    #"options": {"problemType": "mip", "solver":"glpk","debug": True}
                    "options": {"problemType": "mip", "solver":"gurobi_direct", "debug": True}
                    })
                optOutput = model(optAnswer_minObj["solution"])
                minObj = objsFunc(optOutput)[obj]
            # optimizing the objective to find its Maximum value
                optAnswer_maxObj = dgal.max({
                    "model": model,
                    "input": input,
                    "obj": lambda o: objsFunc(o)[obj],
                    "constraints": lambda o: dgal.all([ constraints(o), objsFunc(o)[obj] <= objsSchema[obj]["ub"]]),
                    #"options": {"problemType": "mip", "solver":"glpk","debug": True}
                    "options": {"problemType": "mip", "solver":"gurobi_direct", "debug": True}
                    })
                optOutput = model(optAnswer_maxObj["solution"])
                maxObj = objsFunc(optOutput)[obj]

            else:                           # a maximization metric
            # optimizing the objective to find its Maximum value
                optAnswer_maxObj = dgal.max({
                    "model": model,
                    "input": input,
                    "obj": lambda o: objsFunc(o)[obj],
                    "constraints": constraints,
                    #"options": {"problemType": "mip", "solver":"glpk","debug": True}
                    "options": {"problemType": "mip", "solver":"gurobi_direct", "debug": True}
                    })
                optOutput = model(optAnswer_maxObj["solution"])
                maxObj = objsFunc(optOutput)[obj]
            # optimizing the objective to find its Minimum value
                optAnswer_minObj = dgal.min({
                    "model": model,
                    "input": input,
                    "obj": lambda o: objsFunc(o)[obj],
                    "constraints": lambda o: dgal.all([ constraints(o) , objsFunc(o)[obj] >= objsSchema[obj]["lb"]]),
                    #"options": {"problemType": "mip", "solver":"glpk","debug": True}
                    "options": {"problemType": "mip", "solver":"gurobi_direct", "debug": True}
                    })
                optOutput = model(optAnswer_minObj["solution"])
                minObj = objsFunc(optOutput)[obj]

            minMaxObjs.update({obj :{"min":minObj, "max": maxObj} })
            #minMaxObjs[obj]= {"min":minObj, "max": maxObj}

        vtSpecSet_minMaxObjs.append(minMaxObjs)

    # Initialize a dictionary to hold the min/max values for each obj in the vtSpecSet_minMaxObjs list
    result = {}

    # Iterate through each minMaxObjs dictionary in the vtSpecSet_minMaxObjs list
    for dict in vtSpecSet_minMaxObjs:
        for key, value in dict.items():
            if key not in result:
                # If the key doesn't exist in result, initialize it with infinities
                result[key] = {"min": inf, "max": -inf}
            # Update the minimum value
            result[key]["min"] = min(result[key]["min"], value["min"])
            # Update the maximum value
            result[key]["max"] = max(result[key]["max"], value["max"])

    #print("vtSpecSet_minMaxObjs: ", vtSpecSet_minMaxObjs)
    #print("##########")
    #print("minMaxObjs: ", result)

    return result

#-------------------------------------------------------------------------------

with open(dir+"config.json", "r") as f:
    config = json.load(f)

# extract objectives schema from reqSpec
objsSchema = extractObjsSchema(config)

weightsList = generateWeights(objsSchema, config["settings"]["alpha_entries"], config["settings"]["alpha_epsilon"])
#print(weightsList)
#print(len(weightsList))

minMaxObjs = computeMinMax(objsSchema, config)
#print(minMaxObjs)

podb.paretoOptimalDB(config, weightsList, minMaxObjs)

#-------------------------------------------------------------------------------
