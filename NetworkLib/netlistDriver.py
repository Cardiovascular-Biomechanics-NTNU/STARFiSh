"""Host lifecycle for a Starfish domain coupled to NumPy netlist circuits.

The domain callback owns vessel/characteristic numerics. Circuit preparation
and acceptance follow pureZeroDDriver: init once, observational steps, finalize
once, then output. No generated zero-D replacement is constructed here.
"""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class OneDTimestep:
    index: int
    time: float
    dt: float

    @property
    def end_time(self):
        return self.time + self.dt


class OneDDriver:
    def __init__(self, manager, dt, enforce_consecutive=True):
        if not math.isfinite(dt) or dt <= 0:
            raise ValueError("one-dimensional driver requires positive finite dt")
        self.manager = manager
        self.dt = float(dt)
        self.enforce_consecutive = enforce_consecutive
        self.accepted_steps = 0
        self.prepared = None
        self._has_candidate = False
        self._failed = False

    def iter_init(self, index, time, dt):
        if self._failed:
            raise RuntimeError("one-dimensional timestep failed; close this simulation")
        if self.prepared is not None:
            raise RuntimeError("one-dimensional timestep is already prepared")
        if (type(index) is not int or index < 0 or dt != self.dt
                or not math.isfinite(time)
                or not math.isclose(time, index * dt, rel_tol=1e-12, abs_tol=1e-14)):
            raise ValueError("invalid one-dimensional timestep index, start time or dt")
        if self.enforce_consecutive and index != self.accepted_steps:
            raise RuntimeError("one-dimensional timesteps must be consecutive")
        try:
            self.manager.start_timestep(index, time, dt)
        except Exception:
            self._failed = True
            raise
        self.prepared = OneDTimestep(index, float(time), self.dt)
        self._has_candidate = False
        return self.prepared

    def iter_step(self, advance_domain):
        if self._failed or self.prepared is None:
            raise RuntimeError("prepare a healthy one-dimensional timestep before solving")
        try:
            candidate = advance_domain()
        except Exception:
            self._failed = True
            raise
        self._has_candidate = True
        return candidate

    def iter_finalize(self):
        if self._failed or self.prepared is None or not self._has_candidate:
            raise RuntimeError("cannot accept without a complete current domain step")
        try:
            self.manager.finalize_timestep(self.prepared.index)
        except Exception:
            self._failed = True
            raise
        self.accepted_steps += 1
        self.prepared = None
        self._has_candidate = False
