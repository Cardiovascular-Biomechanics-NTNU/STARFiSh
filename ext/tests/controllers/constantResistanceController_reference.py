"""NumPy equivalent of the retained Python-2 doubling-resistance fixture."""

import numpy as np
from ControllerProtocol_reference import ControllerProgram, ControllerResult


CONTROLLER_API_VERSION = "1"
CONTROLLER_PRIORITY = 0


def build_controller_program():
    def initialize():
        return np.float64(0.0), np.int64(0)

    def update(parameters, state, inputs):
        return ControllerResult(inputs.current_target_values * 2.0,
                                state + np.int64(1), {})

    return ControllerProgram("doubling_resistance", 1, initialize, update, {})
