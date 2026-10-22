"""Synthetic SI upstream consumer of this update's downstream broadcast."""
import numpy as np
from ControllerProtocol_reference import ControllerProgram, ControllerResult

CONTROLLER_API_VERSION = "1"
CONTROLLER_PRIORITY = 1


def build_controller_program():
    def initialize():
        return np.float64(1e7), np.int64(0)

    def update(parameters, state, inputs):
        resistance = parameters * (1. + 1e-6*inputs.broadcasts["down_pressure"])
        return ControllerResult(np.asarray([resistance]), state+np.int64(1), {})

    return ControllerProgram("port_resistance", 1, initialize, update, {})
