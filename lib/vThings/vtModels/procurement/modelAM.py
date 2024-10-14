
import lib.dgal_lib.dgalPy as dgal

def am(input):
    print("input: ", input)
    demand = input["demand"]
    purchaseInfo = input["purchaseInfo"]
    ppu = purchaseInfo["ppu"]
    co2pu = purchaseInfo["co2pu"]
    manufTimePu = purchaseInfo["manufTimePu"]
    available = purchaseInfo["available"]
    qty = purchaseInfo["qty"]

    cost = sum([ppu[s][i] * qty[s][i] for s in qty for i in qty[s]])
    co2 = sum([co2pu[s][i] * qty[s][i] for s in qty for i in qty[s]])
    manufTime = sum([manufTimePu[s][i] * qty[s][i] for s in qty for i in qty[s]])

    constrSeq = [qty[s][i] >= 0 for s in qty for i in qty[s]]

    nonNegQtysConstraint = dgal.all(constrSeq)

    availabilityConstraint = dgal.all([qty[s][i] <= available[s][i] for s in qty for i in qty[s]])

    supply = {}
    for i in demand: supply.update({i: sum(qty[s][i] for s in qty)})

    demandSatisfiedConstraint = dgal.all([demand[i] <= supply[i] for i in demand])
    constraints = dgal.all([nonNegQtysConstraint, availabilityConstraint, demandSatisfiedConstraint])

    return {
        "cost": cost,
        "co2": co2,
        "manufTime": manufTime,
        "constraints": constraints,
        "debug": {
            "supply": supply,
            "availabilityConstraint": availabilityConstraint,
            "demandSatisfiedConstraint": demandSatisfiedConstraint
        }
    }
