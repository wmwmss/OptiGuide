
import lib.dgal_lib.dgalPy as dgal

def objs(o):
    return {
        "cost": o["cost"],
        "co2": o["co2"],
        "manufTime": o["manufTime"]
    }

def consts(o):
    return o["constraints"]
