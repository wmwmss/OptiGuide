import re
import numpy as np
import os
import json
import importlib
from scipy.spatial import distance
import sys
import lib.dgal_lib.dgalPy as dgal
from lib.vThings.vtOperators.vtFunctions import vtOptimalInstance


print(f"Python version: {sys.version}")
print(f"Python path: {sys.path}")
try:
    from sklearn_extra.cluster import KMedoids
    print("Successfully imported KMedoids")
    print(f"sklearn_extra version: {importlib.import_module('sklearn_extra').__version__}")
except ImportError as e:
    print(f"Error importing KMedoids: {e}")
    print("sklearn_extra is not installed or not accessible.")
    from sklearn.cluster import KMeans
    print("Using KMeans as a fallback.")

# new dir
dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")) + "/"
# original dir
#dir="/Users/talmanie/Desktop/OptiGuide/config_procurement/"

#-------------------------------------------------------------------------------
# Unifying entries of initial DB with the similar objectives by applying five steps:
# 1- sort the entries' list by objective dictionaries using Euclidean distance.
# 2- group the similar objective dictionaries from the sorted list using Euclidean distance and a specified epsilon.
# 3- find the representitive weight dictionary for each group using K-Medoids clustering, and get its related objective dictionary.
# 4- use the original index of the representitive data point to extract the associated utility, input and output from the initialDB and generate an entry to the constructed paretoDB.
# 5- sort the generated paretoDB by weight vectors using Euclidean distance. --> canceled
def unifyParetoEntries(initialDB, objsSchema, uniEpsilon):
    # step#1 >
    #extract from the initialDB: all objective dictionaries, their related weights, and the index for each
    entries_list=[{"index": p["index"], "objectives":p["objectives"], "weights":p["weights"]} for p in initialDB]
    # define the reference point
    reference_point = [ 0 for i in range(len(objsSchema))]
    # sort the list of objective dictionaries based on their Euclidean distance to the reference point
    sorted_list = sorted(entries_list, key=lambda x: distance.euclidean(list(x["objectives"].values()), reference_point))
    #print(sorted_list)

    # step#2 >
    # define the maximum distance between any pair of objective dictionaries for each group
    max_distance = uniEpsilon
    # group the similar objective dictionaries in the sorted list based on the specified maximum distance value and using Euclidean distance
    groups = []
    current_group = [sorted_list[0]]
    for i in range(1, len(sorted_list)):
        if distance.euclidean(list(sorted_list[i]["objectives"].values()), list(current_group[0]["objectives"].values())) <= max_distance:
            current_group.append(sorted_list[i])
        else:
            groups.append(current_group)
            current_group = [sorted_list[i]]
    groups.append(current_group)

    # print the groups of similar objective dictionaries and their weights and original indices
    for i, group in enumerate(groups):
        print(f"Group {i+1}:")
        for dict in group:
            print("index:", dict["index"],"| objectives:", dict["objectives"], "| weights:", dict["weights"])
        print()

    paretoDB = []
    for group in groups:
        # convert weight dictionaries to numpy array
        data = np.array([list(d["weights"].values()) for d in group])

        try:
            # Try to use KMedoids if available
            kmedoids = KMedoids(n_clusters=1, metric='euclidean', random_state=0)
            kmedoids.fit(data)
            medoid_index = kmedoids.medoid_indices_[0]
            medoid = group[medoid_index]
        except NameError:
            # If KMedoids is not available, use KMeans as a fallback
            kmeans = KMeans(n_clusters=1, random_state=0)
            kmeans.fit(data)
            centroid = kmeans.cluster_centers_[0]
            # Find the closest point to the centroid
            medoid_index = np.argmin(np.sum((data - centroid)**2, axis=1))
            medoid = group[medoid_index]

        original_index = medoid["index"]

        print("Medoid index:", medoid_index)
        print("Medoid:", medoid)

        # step#4 >
        paretoDB.append({
            "index": groups.index(group),
            "utility": initialDB[original_index]["utility"],
            "weights": medoid["weights"],
            "input": initialDB[original_index]["input"],
            "output": initialDB[original_index]["output"],
            "objectives": medoid["objectives"],
            "norm_objectives": initialDB[original_index]["norm_objectives"]
            })

    # step#5 > canceled because all the weight vectors have the same Euclidean ditance
    # sort the generated paretoDB by the weight vectors using their Euclidean distance to the reference point
    #sorted_paretoDB = sorted(paretoDB, key=lambda x: distance.euclidean(list(x["weights"].values()), reference_point))
    # print([distance.euclidean(list(p["weights"].values()), reference_point) for p in paretoDB])
    # update the index based on the sorted list
    #[p.update({"index":sorted_paretoDB.index(p)}) for p in sorted_paretoDB]
    #paretoDB=sorted_paretoDB

    f = open("paretoDB.json","w")
    f.write(json.dumps(paretoDB))

#-------------------------------------------------------------------------------

# normalize the objective in the range [0-1]
def normObjectives(objectives, objsSchema, minMaxObjs):
    normalizedObjs={}
    for obj in objectives:
        if objsSchema[obj]["minMax"]=="min": # for a minimization metric
            normObj= (minMaxObjs[obj]["max"]-objectives[obj])/(minMaxObjs[obj]["max"]-minMaxObjs[obj]["min"])
        else:                          # for a maximization metric
            normObj= (objectives[obj]-minMaxObjs[obj]["min"])/(minMaxObjs[obj]["max"]-minMaxObjs[obj]["min"])

        normalizedObjs.update({obj :normObj })
    return normalizedObjs

#-------------------------------------------------------------------------------
# Generate optimal Pareto Preprocessing Structure
def paretoOptimalDB(config, wList, minMaxObjs):

    # extract input from config json
    f = open(dir+config["input"],"r")
    input = json.loads(f.read())

    # extract model from vtSpec
    from lib.optiguide_lib.mainPreprocessing import extractModel
    model = extractModel(config)

    # extract objectives schema from reqSpec
    from lib.optiguide_lib.mainPreprocessing import extractObjs
    objsSchema = extractObjs()

    # extract objectives & constraints function from config json
    objs_consts_comp = config["folder"]+ "." + config["objs_consts_comp"]
    conf = importlib.import_module(objs_consts_comp)

    # change to vtOptimalInstance, prepare input artifacts
    with open(dir+config["vtSpec"],"r") as f:
        vtSpec = json.load(f)
    # Create vtSpecNew with the model, input fields replaced
    vtSpecNew = vtSpec.copy()
    vtSpecNew["model"] = model
    vtSpecNew["parametersSchema"] = input
    # Create vtReqSpecNew with the objectives function, constraints replaced
    with open(dir+config["reqSpec"],"r") as f:
        vtReqSpec = json.load(f)
    vtReqSpecNew = vtReqSpec.copy()
    vtReqSpecNew["objectives"]["function"] = conf.objs
    vtReqSpecNew["constraints"] = conf.consts

    # Construct initialDB list that contains all possible feasible solutions
    initialDB = list()
    for i in range(len(wList)):
        def utility(o):
            normObjs= normObjectives(conf.objs(o),objsSchema, minMaxObjs)
            return sum([ normObjs[obj] * wList[i][obj] for obj in normObjs])    # / sum([wList[i][obj] for obj in normObjs])

        # change to vtOptimalInstance
        optAnswer = vtOptimalInstance(vtSpecNew, vtReqSpecNew, utility, options = None)
        # original code
        # optAnswer = dgal.max({
        #     "model": model,
        #     "input": input,
        #     "obj": utility,
        #     "constraints": lambda o: conf.consts(o),
        #     #"options": {"problemType": "mip", "solver":"glpk","debug": True}
        #     "options": {"problemType": "mip", "solver":"gurobi_direct", "debug": True}
        #     })
        optInput = optAnswer["solution"]
        optOutput = model(optInput)
        objectives = conf.objs(optOutput)
        initialDB.append({
            "index": i,
            "utility": utility(objectives),
            "weights": wList[i],
            "input": optInput,
            "output": optOutput,
            "objectives": objectives,
            "norm_objectives": normObjectives(objectives, objsSchema, minMaxObjs)
            })

    f = open("initialDB.json","w")
    f.write(json.dumps(initialDB))

    unifyParetoEntries(initialDB, objsSchema, config["unifyObjs_epsilon"])

#-------------------------------------------------------------------------------
