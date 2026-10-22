from CRIMSONPython import *
from os.path import abspath

class parameterController(abstractParameterController):

	def __init__(self, baseNameOfThisScriptAndOfRelatedFlowOrPressureDatFile, MPIRank):
		abstractParameterController.__init__(self,baseNameOfThisScriptAndOfRelatedFlowOrPressureDatFile, MPIRank)
		self.controllerPriority = -2
		self.stepIndex = 0
		self.flow_history_file = abspath("injured_vessel_flow_history.dat")
		open(self.flow_history_file, "w").close()
		self.finishSetup()

	def updateControl(self, currentParameterValue, delt, dictionaryOfPressuresByNodeIndex, dictionaryOfFlowsByComponentIndex, dictionaryOfVolumesByComponentIndex):
		self.stepIndex += 1
		threeDInterfaceComponentIndex = 1
		observedFlow = dictionaryOfFlowsByComponentIndex[threeDInterfaceComponentIndex]

		self.clearBroadcastData()
		self.addBroadcastVariable("injured_vessel_flow", observedFlow)

		if self.stepIndex % 50 == 0:
			with open(self.flow_history_file, "a") as output_file:
				output_file.write("{} {:.17g}\n".format(self.stepIndex, observedFlow))

		unchangedPressureAtNode2 = dictionaryOfPressuresByNodeIndex[2]
		return unchangedPressureAtNode2
