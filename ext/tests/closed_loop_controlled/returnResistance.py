"""Legacy native C++ counterpart; validation only."""
from CRIMSONPython import *
from math import sin, pi


class parameterController(abstractParameterController):
    def __init__(self, baseNameOfThisScriptAndOfRelatedFlowOrPressureDatFile, MPIRank):
        abstractParameterController.__init__(self, baseNameOfThisScriptAndOfRelatedFlowOrPressureDatFile, MPIRank)
        self.controllerPriority = 0
        self.time = 0.0
        self.finishSetup()

    def setFirstTimestepBroadcastValues(self):
        self.clearBroadcastData()
        self.addBroadcastVariable("down_pressure", 8000.0)

    def updateControl(self, currentParameterValue, delt, dictionaryOfPressuresByNodeIndex,
                      dictionaryOfFlowsByComponentIndex, dictionaryOfVolumesByComponentIndex):
        self.time += delt
        pressure = dictionaryOfPressuresByNodeIndex[1]
        self.clearBroadcastData()
        self.addBroadcastVariable("down_pressure", pressure)
        return 1e8 * (1.0 + .01*sin(2.0*pi*self.time) + 1e-6*pressure)
