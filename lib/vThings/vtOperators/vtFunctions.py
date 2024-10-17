# DG-ViTh Functions
import sys
import copy
import os
import importlib.util
import json

import pyomo.environ as pyo
from pyomo.environ import *

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, project_root)

from lib.vThings.vtOperators.utils import (
    specRefConvertor,
    flowRefConvertor,
    prodRefConvertor,
    getModelRef,
    refConvertor,
    instantiator,
    dgalPathGenerator,
    metricSchemaConstraints,
    objSchemaConstraints
)

# from utils import specRefConvertor
# from utils import flowRefConvertor
# from utils import prodRefConvertor
# from utils import getModelRef

# from utils import refConvertor
# from utils import instantiator

# from utils import dgalPathGenerator
# from utils import metricSchemaConstraints
# from utils import objSchemaConstraints

from lib.dgal_lib import dgalPy as dgal

#-------------------------------------------------------------------------------

# helper functions to construct bound constraints
def constructBoundConstraints(schemaAndBounds, input, constraints=[]):
    # helper function to traverse through schema and input
    # exit case, dgal type structure
    def atomicBoundConstraint(atomicSchema, atomicInput):
        constraints = True
        print("atomicBoundConstraint atomicSchema: "+str(atomicSchema))
        print("atomicBoundConstraint atomicInput: "+str(atomicInput))
        if "lb" in atomicSchema:
            constraints = dgal.all([constraints, atomicInput >= atomicSchema["lb"]])
        if "ub" in atomicSchema:
            constraints = dgal.all([constraints, atomicInput <= atomicSchema["ub"]])
        print("atomicBoundConstraint constraints: "+str(constraints))
        return constraints

    def isDgalType(input):
        if isinstance(input, dict):
            return ("dgalType" in input)
        else:
            return False
    # recursively extract constraints
    if isDgalType(schemaAndBounds):
        constraints = dgal.all([constraints, atomicBoundConstraint(schemaAndBounds, input)])
    elif isinstance(schemaAndBounds, dict):
        for key in schemaAndBounds:
            if key == "@context":
                continue
            if key not in input:
                raise Exception("Key: "+str(key)+" not in input")
            else:
               constraints = constructBoundConstraints(schemaAndBounds[key], input[key], constraints)
    elif isinstance(schemaAndBounds, list):
        schemaLen = len(schemaAndBounds)
        inputLen = len(input)
        for i in range(schemaLen):
            if i >= inputLen:
                raise Exception("schemaLen and inputLen not equal")
        else:
            constraints = constructBoundConstraints(schemaAndBounds[i], input[i], constraints)
    return constraints

# wrapper function to construct bound constraints
def boundConstraints(schemaAndBounds, input):
    constraints = constructBoundConstraints(schemaAndBounds, input, [])
    print("boundConstraints constraints: "+str(constraints))
    return constraints

#-------------------------------------------------------------------------------

# find optimal vt instance
# U maps obj to a number, either min or max
def vtOptimalInstance(vtSpec, vtReqSpec, utility, options = None):
    # extract AM
    model = vtSpec["model"]
    # extract model input
    input = vtSpec["parametersSchema"]
    # extract obj function
    objectives = vtReqSpec["objectives"]["function"]
    objsSchemaAndBounds = vtReqSpec["objectives"]["schema"]

    # get utility function from wList and normObjs
    # o is output of the model
    # def utilityFunction(o):
    #     objs = objectives(o)
    #     utilityValue = sum([objs[obj]*utility["weights"][obj] for obj in objsSchemaAndBounds])
    #     return utilityValue

    #minMaxFlag = utility["minMax"]
    # normalized objs, always max utility
    minMaxFlag = "max"

    def constraints(o):
        modelComputedConstraints = o["constraints"]
        # possibly implement in DGAL, assuming we have it here
        if "metricSchema" in vtSpec:
            vtMetricBounds = boundConstraints(vtSpec["metricSchema"],o)
        else:
            vtMetricBounds = True
        if "metricSchema" in vtReqSpec:
            reqMetricBounds = boundConstraints(vtReqSpec["metricSchema"],o)
        else:
            reqMetricBounds = True
        objs = objectives(o)
        objsBounds = boundConstraints(objsSchemaAndBounds, objs)
        constraints = dgal.all([
            modelComputedConstraints,
            vtMetricBounds,
            reqMetricBounds,
            objsBounds
        ])
        return(constraints)

    def obj(o):
        return utility(objectives(o))

    vtOptimal = dgal.optimize(
        model,
        input,
        minMaxFlag,
        # utilityFunction,
        obj,
        constraints,
        # options
        {"problemType": "mip", "solver":"gurobi_direct","debug": True}
    )
    return vtOptimal
