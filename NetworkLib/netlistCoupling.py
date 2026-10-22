"""Simultaneous 1D characteristic coupling at frozen netlist state.

Derived Starfish infrastructure. Equations and signs are documented in
docs/netlist_closed_loop_implementation_plan.md, sections 7 and 8. This module
does not advance circuits, controllers, valves, vessel arrays or histories.
"""

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class CharacteristicPacket:
    surface_id: int
    position: int
    flow_sign: float
    timestep: int
    memory_index: int
    dt: float
    pressure: float
    axial_flow: float
    area: float
    transform: np.ndarray
    known_increment: float

    def __post_init__(self):
        if (type(self.surface_id) is not int or self.surface_id < 0
                or type(self.timestep) is not int or self.timestep < 0
                or type(self.memory_index) is not int or self.memory_index < 0):
            raise ValueError("packet IDs and indices must be nonnegative integers")
        if self.position not in (0, -1) or self.flow_sign not in (-1.0, 1.0):
            raise ValueError("packet requires endpoint 0/-1 and flowSign +1/-1")
        values = (self.dt, self.pressure, self.axial_flow, self.area, self.known_increment)
        if not all(math.isfinite(value) for value in values) or self.dt <= 0 or self.area <= 0:
            raise ValueError("packet state must be finite with positive dt and area")
        matrix = np.array(self.transform, dtype=np.float64, copy=True)
        if matrix.shape != (2, 2) or not np.isfinite(matrix).all():
            raise ValueError("characteristic transform must be finite and 2 by 2")
        matrix.setflags(write=False)
        object.__setattr__(self, "transform", matrix)

    def coefficients(self):
        unknown, known = (0, 1) if self.position == 0 else (1, 0)
        r = self.transform
        return (self.pressure + r[0, known] * self.known_increment,
                r[0, unknown],
                self.flow_sign * (self.axial_flow + r[1, known] * self.known_increment),
                self.flow_sign * r[1, unknown])


@dataclass(frozen=True)
class CoupledBoundarySolution:
    surface_ids: tuple
    timestep: int
    pressures: np.ndarray
    flows: np.ndarray
    increments: tuple
    characteristics: tuple
    matrix: np.ndarray
    rhs: np.ndarray
    scaled_backward_error: float


def solve_characteristics(packets, response, flow_input_mask):
    """Solve all endpoints together, including general pressure-input ports.

    response uses external netlist flow coordinates, including circuit-internal
    orientation already. Starfish flowSign is applied only in packet coefficients.
    Row/column equilibration avoids mixing pressure/flow magnitudes in the solve.
    """
    packets = tuple(packets)
    if not packets:
        raise ValueError("at least one characteristic packet is required")
    ids = tuple(packet.surface_id for packet in packets)
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate characteristic surface")
    first = packets[0]
    if any((p.timestep, p.memory_index, p.dt) !=
           (first.timestep, first.memory_index, first.dt) for p in packets):
        raise ValueError("all packets must use the same timestep, memory index and dt")
    count = len(packets)
    modes = np.asarray(flow_input_mask)
    if modes.shape != (count,) or modes.dtype != np.bool_:
        raise ValueError("flow-input mask must be a Boolean vector in packet order")
    hp, hq, p0, q0 = (np.asarray(value, dtype=np.float64) for value in (
        response.pressure_response, response.flow_response,
        response.pressure_offset, response.flow_offset))
    if (hp.shape != (count, count) or hq.shape != hp.shape
            or p0.shape != (count,) or q0.shape != p0.shape
            or any(not np.isfinite(x).all() for x in (hp, hq, p0, q0))):
        raise ValueError("port responses must be finite and match packet order")
    a, b, c, d = np.asarray([p.coefficients() for p in packets]).T
    dp, dq = np.diag(b), np.diag(d)
    f = np.diag(modes.astype(np.float64))
    t = np.eye(count) - f
    uc, du = f @ c + t @ a, f @ dq + t @ dp
    matrix = f @ (dp - hp @ du) + t @ (dq - hq @ du)
    rhs = f @ (p0 + hp @ uc - a) + t @ (q0 + hq @ uc - c)
    if not np.isfinite(matrix).all() or not np.isfinite(rhs).all():
        raise FloatingPointError("nonfinite coupled boundary equations")
    row_norm = np.max(np.abs(matrix), axis=1)
    if np.any(row_norm == 0):
        raise np.linalg.LinAlgError("coupled boundary system has a zero equation row")
    row_scaled = matrix / row_norm[:, None]
    col_norm = np.max(np.abs(row_scaled), axis=0)
    if np.any(col_norm == 0):
        raise np.linalg.LinAlgError("coupled boundary system has an unconstrained unknown")
    scaled, scaled_rhs = row_scaled / col_norm[None, :], rhs / row_norm
    y = np.linalg.solve(scaled, scaled_rhs)
    unknown = y / col_norm
    denominator = np.linalg.norm(scaled, np.inf) * np.linalg.norm(y, np.inf) + np.linalg.norm(scaled_rhs, np.inf)
    residual = np.linalg.norm(scaled @ y - scaled_rhs, np.inf)
    backward_error = float(residual / denominator if denominator else residual)
    if not np.isfinite(unknown).all() or not math.isfinite(backward_error) or backward_error > 5e-12:
        raise FloatingPointError("coupled boundary solve failed its scaled residual check")
    pressures, flows = a + b * unknown, c + d * unknown
    increments, characteristics = [], []
    for packet, value in zip(packets, unknown):
        omega = np.asarray([value, packet.known_increment] if packet.position == 0
                           else [packet.known_increment, value])
        increments.append(packet.transform @ omega)
        characteristics.append(omega)
    return CoupledBoundarySolution(ids, first.timestep, pressures, flows,
                                   tuple(increments), tuple(characteristics), matrix, rhs, backward_error)


class ClosedLoopBoundaryGroup:
    """Prepare all endpoints, solve once, validate all, then scatter all."""

    def __init__(self, manager, boundaries, dt):
        self.manager = manager
        self.adapter = manager._get_adapter(dt)
        self.boundaries = dict(boundaries)
        if set(self.boundaries) != set(self.adapter.surface_ids):
            raise ValueError("closed-loop boundary objects do not cover the circuit ports")
        self.adapter.endpoint_bindings = [dict(surface_id=surface, **manager.boundaries[surface])
                                          for surface in self.adapter.surface_ids]
        self.last_solution = None

    def __call__(self):
        packets = tuple(self.boundaries[surface].prepare_netlist_packet(
            surface, self.manager.boundaries[surface]["flow_sign"])
            for surface in self.adapter.surface_ids)
        first = packets[0]
        time = (first.timestep + 1) * first.dt
        response = self.adapter.probe_port_response(first.timestep, time, first.dt,
            [p.flow_sign * p.axial_flow for p in packets], [p.pressure for p in packets])
        if response.surface_ids != tuple(p.surface_id for p in packets):
            raise ValueError("circuit response order differs from characteristic packet order")
        solution = solve_characteristics(packets, response, response.flow_input_mask)
        trial = self.adapter.solve_trial(first.timestep, time, first.dt,
                                         solution.flows, solution.pressures)
        if (not np.allclose(solution.pressures, trial.pressures, atol=1e-8, rtol=5e-11)
                or not np.allclose(solution.flows, trial.flows, atol=1e-12, rtol=5e-11)):
            raise FloatingPointError("simultaneous endpoints disagree with the full circuit solve")
        prepared = [self.boundaries[p.surface_id].prepare_netlist_result(p, du, omega)
                    for p, du, omega in zip(packets, solution.increments, solution.characteristics)]
        self.adapter.stage_trial(trial)
        for packet, result in zip(packets, prepared):
            self.boundaries[packet.surface_id].apply_boundary_result(result)
        for surface, pressure, flow in zip(solution.surface_ids, solution.pressures, solution.flows):
            self.manager.record_boundary_state(surface, first.timestep, time, first.dt,
                                                float(pressure), float(flow))
        self.last_solution = solution
