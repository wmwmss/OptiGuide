'''
extentions TBD:
---------------
1. additional Pyomo dvar types (not just real? and int?); also add optional lower and upper bounds for each declared var
2. if Pyomo constraintSeq evaluates to True, make sure that the empty seq is traversed to Pyomo;
   if evaluates to False, return dgalStatus within status of optAnswer
3. add dvar arrays, so that they can be specified in a compact way in var input
4. Add piece-wise linear function in Python to be translated into Pyomo piece-wise linear function



'''
import pdb
import copy
import json
import pyomo.environ as pyo
from pyomo.environ import *
from pyomo.opt import SolverFactory
from pyomo.opt import SolverStatus, TerminationCondition

import logging
logging.basicConfig(filename= "dgalDebug.log", level=logging.DEBUG)
#--------------------------------------------------------------------------
def startDebug():
    f = open("debug.log","w")
    f.write("\nNEW RUN \n--------\n")

def debug(mssg,var):
    f = open("debug.log","a")
    f.write("\n\nDEBUG: ")
    f.write(str(mssg))
    f.write(":\n")
    f.write(str(var))
#---------------------------------------------------------------------------
'''
def debug(mssg,var):
    pass
'''
#--------------------------------------------------------------------------

def merge(dictSeq):
    merged = dict()
    for i in dictSeq:
        merged.update(i)
    return merged
#--------------------------------------------------------------
'''
constraintSeq is a (possibly empty) list of elements, each being either
- bool
- pyomo atomic constraint or
- sequence of pyomo atomic constraints
The function returns either bool (True or False) or
a non-empty (flat) sequence of pyomo atomic constraints
'''
def all(constraintSeq):
#    debug("constraintSeq", constraintSeq)
    # pdb.set_trace()
    constraint = []
#    debug("emptyConstraintList", constraint)
    for c in constraintSeq:
#        debug("constraintList_beg_of_iteration", constraint)
#        debug("type of c",type(c))
        if type(c) == bool:
            if c == True:
#                debug("c_if_true", c)
                pass
            elif c == False:
#                debug("c_if_false", c)
                return False
            else: print("dgal.all: bool type error")
        elif type(c) == list:  # i.e., it is flat seq of Pyomo constraints
                c1 = all(c)
                if type(c1) == bool:
                    if c1 == True: pass
                elif c1 == False: return False
                else: constraint.extend(c1)
        else:  # i.e., it is a pyomo atomic constraint
            constraint.append(c)
#        debug("constraintList_end_of_iteration", constraint)
#    debug("constraintList_after_loop", constraint)
    if constraint == []: return True
    else: return constraint

# tbd note: find out how to override Python all, any, and, or operators
#--------------------------------------------------------------------------
def dgalType(input):
    if type(input) == dict and "dgalType" in input.keys():
        if input["dgalType"] == "real?":
            return "real?"
        elif input["dgalType"] == "int?":
            return "int?"
    else:
        return "none"
#--------------------------------------------------------------------------
# initially invoked with counts = {"int?": -1, "real?": -1}
def enumDgalVars(input, counts):
    dgalVarFlag = dgalType(input)
    if dgalVarFlag == "real?":
            counts["real?"] += 1
            input["index"] = counts["real?"]
    elif dgalVarFlag == "int?":
            counts["int?"] += 1
            input["index"] = counts["int?"]
    elif type(input) == dict:
        for key in input:
            enumDgalVars(input[key],counts)
    elif type(input) == list or type(input) == set:
        for obj in input:
            enumDgalVars(obj,counts)
#-------------------------------------------------------------------------------------------------
#    -- assumes that pyomoModel has two var arrays: real[] and int[] with the numbers corresponding to counts;
#    -- assumes that counts capture the top index for "real?" and "int?" arrays
#    -- traverse input and replace dgalVarTypes with pyomo model variables
#    -- pyomo model should have sufficient length of real and int variable arrays to be assigned
#    -- to dgalType vars

def putPyomoVars(input, pyomoModel):
    dgalVar = dgalType(input)
    if dgalVar == "real?":
        return pyomoModel.real[input["index"]]
    if dgalVar == "int?":
        return pyomoModel.int[input["index"]]
    if type(input) == dict:    #i.e., dict that is not dgalTypes
        for key in input:
            input[key] = putPyomoVars(input[key], pyomoModel)
        return input
    if type(input) == list:
        for i in range(len(input)):
            input[i] = putPyomoVars(input[i], pyomoModel)
        return input
    return input    #can't contain dgalTypes

#-------------------------------------------------------------------------------
#- dgModel: an analytic performance model (AM) a python function
#- enumInput: is a dgalVar enumerated dgModel input
#- objective: is a function that gives value to optimize from output of dgModel
#- minMax: is either "min" or "max" to indicate whether the problem is minimization or
#          maximization of objective
#- constraints: is a function that returns dgalBoolean from output of dgModel;
#             this is going to serve as constraints of the optimization problem
#- config: is a structure with solver / algorithm configuration: for now it
#           is a dict {"solver": solver }, where solver is an available Pyomo solver
def createPyomoModel(dgalModel, enumInputAndCounts, minMax, objective, constraints):
# extract enumInput & counts
    enumInput = enumInputAndCounts["enumInput"]
    counts = enumInputAndCounts["counts"]
# create Pyomo model and vars
    model = ConcreteModel()
    model.realI = RangeSet(0,counts["real?"])
    model.intI = RangeSet(0,counts["int?"])
#    model.real = Var(model.realI, domain=NonNegativeReals)
#    model.int = Var(model.intI, domain=NonNegativeIntegers)
    model.real = Var(model.realI, domain=Reals)
    model.int = Var(model.intI, domain=Integers)
# insert pyomoVars
    inputWithPyomoVars = copy.deepcopy(enumInput)
    putPyomoVars(inputWithPyomoVars,model)
    debug("input w Pyomo vars",inputWithPyomoVars)
#    logging.debug("\n input w Pyomo vars: \n",inputWithPyomoVars)

# run dgModel (AM) on inputWithPyomoVars to get symbolic output
    output = dgalModel(inputWithPyomoVars)
    debug("output of dgalModel", output)
    constraintList = constraints(output)
    obj = objective(output)

# insert constaints and objective into Pyomo Model
    model.dgalConstraintList = constraintList
    model.dgalObjective = obj
    model.constrIndex = RangeSet(0,len(constraintList)-1)
    def pyomoConstraintRule(model, i):
        return model.dgalConstraintList[i]
    def pyomoObjectiveRule(model):
        return(model.dgalObjective)
    model.pyomoConstraint = Constraint(model.constrIndex, rule= pyomoConstraintRule)
    if minMax == "min":
        model.pyomoObjective = Objective(rule=pyomoObjectiveRule, sense=minimize)
    elif minMax == "max":
        model.pyomoObjective = Objective(rule=pyomoObjectiveRule, sense=maximize)
    else: debug("dgal: minMax flag error")
    debug("pyomoModel before return",model)
    return model
#------------------------------------------------------------------------------
# generation of Pyomo abstract model (with parameters), which can be instantiated
# later (and possibly solved)
# returns pyomo abstract model
# will need auxiliary functions of extracting param vector from input, and constructing
# varInput from varParamInput + param vector

def compileDgalModel(dgalModel, varParamInputAndCounts, minMax, objective, constraints):
    skip

#------------------------------------------------------------------------------
# pyomoResult is the result of optimizaiton from Pyomo Solver (in JSON)
# dgalType is either "real?" or "int?"
# index is a non-negative integer indicating position in pyomo var array
# the function returns the value of the corresponding variable
def varValue(pyomoModel,dgalType,index):
    # tbd; in the meantime just mock-up
#    debug("dgalType_in_varValue", dgalType)
#    debug("index_in_varValue", index)
    if dgalType == "real?":
        value = pyo.value(pyomoModel.real[index])
#        debug("real value",value)
    elif dgalType == "int?":
        value = pyo.value(pyomoModel.int[index])
#        debug("int value",value)
    else:
        print("varValue_error: type is neither real? nor int?")
        value = "error"
    return(value)
#---------------------------------------------------------------------
# assumes that pyomoResult has values for all enumerated dgalVars in enumInput
# answers is enumerated input initially, then replaced with corresponding values
# from pyo.values


def dgalOptResult(enumInput,pyomoModel):
    dgType = dgalType(enumInput)
    debug("dgType_in_dgalOptResult", dgType)
    if dgType == "real?" or dgType == "int?":
        debug("passed real? or int? test in dgalOptResult",dgType)
        return varValue(pyomoModel, dgType, enumInput["index"])
    if type(enumInput) == dict:    #i.e., dict that is not dgalTypes
        for key in enumInput:
            debug("key in enumInput:",key)
            enumInput[key] = dgalOptResult(enumInput[key],pyomoModel)
        return enumInput
    if type(enumInput) == list:
        for i in range(len(enumInput)):
            enumInput[i] = dgalOptResult(enumInput[i],pyomoModel)
        return enumInput
    return enumInput  #can't contain dgalTypes

#-----------------------------------------------------------------
# model: pyomoModel w/objective and constraints
# config: is a dictionary with a solver setting, initially just
#          {"solver": solver}
# this function needs to be cleaned, by eliminating writing into files
def solvePyomoModelConstructDgalResult(pyomoModel,enumInput,options):
    debug("solver:", options["solver"])
    opt = SolverFactory(options["solver"])
    # pdb.set_trace()
    results = opt.solve(pyomoModel,tee=True)
    debug("model after solve:",pyomoModel)
# compute status: solver_status and termination_condition
    # pdb.set_trace()
    if  results.solver.status == SolverStatus.ok:
        status = { "solver_status": "ok" }
        if results.solver.termination_condition == TerminationCondition.optimal:
            status["termination_condition"] = "optimal"
        else:
            status["termination_condition"] = str(results.solver.termination_condition)
    else:
        status = {"solver_status": "not_ok"}
# compute optAnswer, if exists, and make it "none" otherwise
    if status["termination_condition"] == "optimal":
#           answer = copy.deepcopy(enumInput)
        # pdb.set_trace()
        optAnswer = dgalOptResult(enumInput,pyomoModel)
        debug("optAnswer before dgalOptResult return",optAnswer)
        # pdb.set_trace()
    else:
        optAnswer = "none"
# compute dgalOutp withut status and answer
    dgalOutput = { "status": status, "solution": optAnswer}
# add report to optAnswer if options request debug
    if "debug" in options and options["debug"]:
        dgalOutput["report"] = produceReport(results)
    return dgalOutput

#--------------------------------------------------------------------------
# I am here: there is a problem with producing a report
def produceReport(results):
#    pyomoModel.solutions.store_to(results)
    debug("pyomo results:",results)
    results.write(filename='result.json', format='json')
    f = open("result.json", "r")
    dictPyomoResult = json.loads(f.read())
    debug("dictPyomoResult read from results file", dictPyomoResult)
    dictPyomoResult["Problem"][0]["Lower bound"] = \
        str(dictPyomoResult["Problem"][0]["Lower bound"])
    dictPyomoResult["Problem"][0]["Upper bound"] = \
        str(dictPyomoResult["Problem"][0]["Upper bound"])
    return dictPyomoResult


#----------------------------------------------------------
#
def optimize(dgalModel,input,minMax,obj,constraints,options):
    # enumerate dgalVars in input
    counts = {"real?": -1, "int?": -1}
    enumInput = copy.deepcopy(input)
    enumDgalVars(enumInput, counts)
    debug("enumInput in py", enumInput)
    enumInputAndCounts = { "enumInput": enumInput, "counts":counts}
    debug("enumInputAndCounts_before_create_Pyomo_model", enumInputAndCounts)
    pyomoModel = createPyomoModel(dgalModel,enumInputAndCounts,minMax,obj,constraints)
    # pdb.set_trace()
    debug("enumInput before solving", json.dumps(enumInput))
    pyomoModel.pprint()
    answer = solvePyomoModelConstructDgalResult(pyomoModel,enumInput,options)
    # pyomoModel.display()
    # pdb.set_trace()
    return answer
# extend for special case when constraints generated are Bool True or False

# def min(model,input,obj,constraints,config):
def min(p):
    optAnswer = optimize( \
        p["model"],p["input"],"min",p["obj"],p["constraints"],p["options"])
    return optAnswer

# def max(model,input,obj,constraints,config):
def max(p):
    optAnswer = optimize( \
        p["model"],p["input"],"max",p["obj"],p["constraints"],p["options"])
    return optAnswer

#---------------------------------------------------------------------------
# model is an analytic model;
# input is a varParInput, i.e., input to the model annoted w/variable and parameters
# metrics is a function that gives a vector of metrics from the model output;
#         It is to be used for PairwisePenalty function, which computes (penatly)  distance
#         between 2 vectors of metrics
# trainingSeq is a list of pairs {inVector:..., metrics: ...}, where inVector is a vector
#         of values corresponding to variables in the model input sorted in the depth-first
#         traversal order; and metrics is a vector of metrics associated with the inVector.
#         The dimension of metrics must be the same as dimension of the metrics function output.
# pairwisePenalty is a function that, given 2 metric vectors, computes the penalty.
#         The computed penalty must be a distance function
# penalty is a function that, given a vector of penalties for each entry in the
#         trainingSeq, computes the overall penalty. Must be a metric function.
# options are options TBD
# NOTE: will need auxiliary functions that compute inVector from a model input,
#       and the other way around, that compute modelInput from varInput and inVector.
#
def train(model,input,metrics,trainingSeq, pairwisePenalty,penalty,options):
    return "tbd"
def calibrate(model, lossfunction, input, output):
    return "tbd"
#
#-----------------------------------------------------------------------------
