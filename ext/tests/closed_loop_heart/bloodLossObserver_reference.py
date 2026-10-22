"""Observe the same local bleed flow and drain pressure as the C++ script."""

import numpy as np
from ControllerProtocol_reference import ControllerProgram, ControllerResult

CONTROLLER_API_VERSION = "1"
CONTROLLER_PRIORITY = -2


def build_controller_program():
    def initialize():
        return (), np.float64(0.0)

    def update(parameters, state, inputs):
        observed_flow = np.float64(inputs.flow[0])  # Local component 1.
        return ControllerResult(
            target_values=np.asarray([inputs.pressure[1]], dtype=np.float64),
            state=observed_flow,
            broadcasts={"injured_vessel_flow": observed_flow},
        )

    return ControllerProgram("bloodLossObserver", 1, initialize, update,
                             {"injured_vessel_flow": np.float64(0.0)})
