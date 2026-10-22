"""Legacy native C++ counterpart; validation only."""
from CRIMSONPython import *


class parameterController(abstractParameterController):
    def __init__(self, baseNameOfThisScriptAndOfRelatedFlowOrPressureDatFile, MPIRank):
        abstractParameterController.__init__(self, baseNameOfThisScriptAndOfRelatedFlowOrPressureDatFile, MPIRank)
        self.controllerPriority = 1
        self.finishSetup()

    def updateControl(self, currentParameterValue, delt, dictionaryOfPressuresByNodeIndex,
                      dictionaryOfFlowsByComponentIndex, dictionaryOfVolumesByComponentIndex):
        pressure = self.getRecievedBroadcastValue("returnResistance", "down_pressure")
        return 1e7 * (1.0 + 1e-6*pressure)
