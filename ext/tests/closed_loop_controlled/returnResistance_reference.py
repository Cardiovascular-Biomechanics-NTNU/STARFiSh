"""Synthetic SI return resistance: old owner pressure and an internal clock."""
import numpy as np
from ControllerProtocol_reference import ControllerProgram, ControllerResult

CONTROLLER_API_VERSION = "1"
CONTROLLER_PRIORITY = 0


def build_controller_program():
    def initialize():
        return np.float64(1e8), np.float64(0.)

    def update(parameters, state, inputs):
        time = state + inputs.dt
        pressure = inputs.pressure[0]
        resistance = parameters * (1. + .01*np.sin(2.*np.pi*time) + 1e-6*pressure)
        return ControllerResult(np.asarray([resistance]), time, {"down_pressure": pressure})

    return ControllerProgram("return_resistance", 1, initialize, update, {"down_pressure": np.float64(0.)})
