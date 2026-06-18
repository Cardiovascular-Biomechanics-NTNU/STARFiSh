from CRIMSONPython import *


class parameterController(abstractParameterController):
    def __init__(self, baseNameOfThisScriptAndOfRelatedFlowOrPressureDatFile, MPIRank):
        abstractParameterController.__init__(
            self,
            baseNameOfThisScriptAndOfRelatedFlowOrPressureDatFile,
            MPIRank)
        self.finishSetup()

    def updateControl(
            self,
            currentParameterValue,
            delt,
            dictionaryOfPressuresByNodeIndex,
            dictionaryOfFlowsByComponentIndex,
            dictionaryOfVolumesByComponentIndex):
        return currentParameterValue * 2.0
