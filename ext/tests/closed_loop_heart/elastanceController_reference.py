"""NumPy controller API translation of this directory's legacy heart law.

The original elastanceController.py remains the C++ controller. Constants,
positive-only loss accumulation, rate limits and cycle timing match it.
Diagnostic file writes are omitted; simulation histories are saved by Starfish.
"""

from math import cos, pi
from typing import NamedTuple

import numpy as np
from ControllerProtocol_reference import ControllerProgram, ControllerResult

CONTROLLER_API_VERSION = "1"
CONTROLLER_PRIORITY = -1


class FeedbackState(NamedTuple):
    periodic_time: float
    heart_period: float
    total_blood_loss: float
    heart_rate: float
    delta_heart_rate: float
    debt_delta: float


def build_controller_program():
    def initialize():
        return (), FeedbackState(0.0, 0.86, 0.0, 60.0 / 0.86, 0.0, 0.0)

    def update(parameters, state, inputs):
        current_rate = 60.0 / state.heart_period
        observed_flow = float(inputs.broadcasts["injured_vessel_flow"])
        total_loss = state.total_blood_loss + max(0.0, float(inputs.dt) * observed_flow)
        debt = 120.0 - current_rate
        delta_rate = 75.0 * debt * total_loss
        delta_rate = max(-5.0, delta_rate)
        delta_rate = min(2.0, delta_rate)

        periodic_time = state.periodic_time + float(inputs.dt)
        heart_period = state.heart_period
        if periodic_time >= heart_period:
            current_rate += delta_rate
            if current_rate > 200.0:
                current_rate = 200.0
            elif current_rate < 40.0:
                current_rate = 40.0
            heart_period = 60.0 / current_rate
            periodic_time -= heart_period
            if periodic_time < 0.0:
                periodic_time = 0.0

        if periodic_time <= 0.2782:
            elastance = 4.10246e6 + 0.5 * (1.0e8 - 4.10246e6) * (
                1.0 - cos((periodic_time * pi) / 0.2782))
        elif periodic_time <= 0.2782 + 0.1391:
            elastance = 4.10246e6 + 0.5 * (1.0e8 - 4.10246e6) * (
                1.0 + cos(((periodic_time - 0.2782) * pi) / 0.1391))
        else:
            elastance = 4.10246e6

        return ControllerResult(
            target_values=np.asarray([elastance], dtype=np.float64),
            state=FeedbackState(periodic_time, heart_period, total_loss,
                                current_rate, delta_rate, debt),
            broadcasts={},
        )

    return ControllerProgram("elastanceController", 1, initialize, update, {})
