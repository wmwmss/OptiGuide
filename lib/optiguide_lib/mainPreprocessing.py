import sys
sys.path.append("/Users/talmanie/Desktop/OptiGuide")
import json
import math
import importlib
from itertools import product
import lib.dgal_lib.dgalPy as dgal
import paretoDB as pdb

dir="/Users/talmanie/Desktop/OptiGuide/config_procurement/"
#dir="/Users/talmanie/Desktop/OptiGuide/config_optiSensor/"

f = open(dir+"config.json", "r")
config = json.loads(f.read())
#-------------------------------------------------------------------------------

# Generate a list of weight combinations for all objectives
def generateWeights(confObjs, num_entries, e):
    weightsList=[]
    objs_except_last = list(confObjs.keys())[:-1]
    last_obj = list(confObjs.keys())[-1]
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
def computeMinMax(config):
    # Extract required data from config json
    f = open(dir+config["input"],"r")
    input = json.loads(f.read())
    model_name= config["folder"]+ "." + config["model"]
    model = importlib.import_module(model_name)
    objs_consts_comp = config["folder"]+ "." + config["objs_consts_comp"]
    conf = importlib.import_module(objs_consts_comp)
    cObjs = config["objs"]

    minMaxObjs = {}
    for obj in cObjs:
        if cObjs[obj]["minMax"]=="min": # a minimization metric
        # optimizing the objective to find its Minimum value
            optAnswer_minObj = dgal.min({
                "model": model.am,
                "input": input,
                "obj": lambda o: conf.objs(o)[obj],
                "constraints": lambda o: conf.consts(o),
                #"options": {"problemType": "mip", "solver":"glpk","debug": True}
                "options": {"problemType": "mip", "solver":"gurobi_direct", "debug": True}
                })
            optOutput = model.am(optAnswer_minObj["solution"])
            minObj = conf.objs(optOutput)[obj]
        # optimizing the objective to find its Maximum value
            optAnswer_maxObj = dgal.max({
                "model": model.am,
                "input": input,
                "obj": lambda o: conf.objs(o)[obj],
                "constraints": lambda o: dgal.all([ conf.consts(o), conf.objs(o)[obj] <= cObjs[obj]["ub"]]),
                #"options": {"problemType": "mip", "solver":"glpk","debug": True}
                "options": {"problemType": "mip", "solver":"gurobi_direct", "debug": True}
                })
            optOutput = model.am(optAnswer_maxObj["solution"])
            maxObj = conf.objs(optOutput)[obj]

        else:                           # a maximization metric
        # optimizing the objective to find its Maximum value
            optAnswer_maxObj = dgal.max({
                "model": model.am,
                "input": input,
                "obj": lambda o: conf.objs(o)[obj],
                "constraints": lambda o: conf.consts(o),
                #"options": {"problemType": "mip", "solver":"glpk","debug": True}
                "options": {"problemType": "mip", "solver":"gurobi_direct", "debug": True}
                })
            optOutput = model.am(optAnswer_maxObj["solution"])
            maxObj = conf.objs(optOutput)[obj]
        # optimizing the objective to find its Minimum value
            optAnswer_minObj = dgal.min({
                "model": model.am,
                "input": input,
                "obj": lambda o: conf.objs(o)[obj],
                "constraints": lambda o: dgal.all([ conf.consts(o) , conf.objs(o)[obj] >= cObjs[obj]["lb"]]),
                #"options": {"problemType": "mip", "solver":"glpk","debug": True}
                "options": {"problemType": "mip", "solver":"gurobi_direct", "debug": True}
                })
            optOutput = model.am(optAnswer_minObj["solution"])
            minObj = conf.objs(optOutput)[obj]

        minMaxObjs.update({obj :{"min":minObj, "max": maxObj} })
        #minMaxObjs[obj]= {"min":minObj, "max": maxObj}
    return minMaxObjs

#-------------------------------------------------------------------------------

#Function Calls
weightsList= generateWeights( config["objs"], config["alpha_entries"], config["alpha_epsilon"])
#print(weightsList)
print(len(weightsList))

minMaxObjs= computeMinMax(config)
print(minMaxObjs)

pdb.paretoDB(config, weightsList, minMaxObjs)

#-------------------------------------------------------------------------------
