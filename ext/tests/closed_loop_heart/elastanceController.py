"""SI blood-loss feedback law from the Starfish tutorial; native validation.

The scalar law is unchanged. Linear buffered CSV output replaces repeated
rewriting of complete diagnostic histories in this NEW case only.
"""
from CRIMSONPython import *
from math import cos, pi


class parameterController(abstractParameterController):
    def __init__(self, baseNameOfThisScriptAndOfRelatedFlowOrPressureDatFile, MPIRank):
        abstractParameterController.__init__(self, baseNameOfThisScriptAndOfRelatedFlowOrPressureDatFile, MPIRank)
        self.controllerPriority = -1
        self.phase = 0.0
        self.period = .86
        self.loss = 0.0
        self.time = 0.0
        self.step = 0
        self.trace = open('heart_controller_trace.csv', 'w', 1)
        self.trace.write('step,time_s,phase_s,period_s,heart_rate_bpm,controller_lost_volume_m3,delta_heart_rate_bpm,debt_bpm,elastance_pa_per_m3\n')
        self.trace.write('0,0,0,.86,{:.17g},0,0,0,4100000\n'.format(60./.86))
        self.finishSetup()

    def updateControl(self, currentParameterValue, delt, dictionaryOfPressuresByNodeIndex,
                      dictionaryOfFlowsByComponentIndex, dictionaryOfVolumesByComponentIndex):
        rate = 60. / self.period
        flow = self.getRecievedBroadcastValue('bloodLossObserver', 'injured_vessel_flow')
        self.loss += max(0.0, delt * flow)
        debt = 120. - rate
        delta = min(2., max(-5., 75. * debt * self.loss))
        self.phase += delt
        if self.phase >= self.period:
            rate = min(200., max(40., rate + delta))
            self.period = 60. / rate
            self.phase -= self.period
            if self.phase < 0.:
                self.phase = 0.
        if self.phase <= .2782:
            elastance = 4.10246e6 + .5*(1.e8 - 4.10246e6)*(1. - cos(self.phase*pi/.2782))
        elif self.phase <= .2782 + .1391:
            elastance = 4.10246e6 + .5*(1.e8 - 4.10246e6)*(1. + cos((self.phase-.2782)*pi/.1391))
        else:
            elastance = 4.10246e6
        self.time += delt
        self.step += 1
        self.trace.write('{} {:.17g} {:.17g} {:.17g} {:.17g} {:.17g} {:.17g} {:.17g} {:.17g}\n'.format(
            self.step, self.time, self.phase, self.period, rate, self.loss, delta, debt, elastance).replace(' ', ','))
        return elastance
