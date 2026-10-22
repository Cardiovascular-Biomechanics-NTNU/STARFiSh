"""Validation-only native C++ backend for the same Starfish endpoint schedule.

Reference topology/identity records are shared host setup. Every response,
accepted circuit solve, history advance and physical observation comes from
the native CRIMSON subsection process. No NumPy circuit solve is used here.
The native worker performs its zero-flow fresh-run RHS bootstrap during LOAD,
without publishing state or accepting history, before arbitrary port probes.
Every frozen QUERY solves twice without publication/acceptance to consume the
same stored-flow guard if an initially blocked port has only just opened.
"""

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from UtilityLib.crimsonNetlistWorkerClient import (
    CrimsonNetlistWorkerClient, _quote_worker_argument,
)
from UtilityLib.netlistClosedLoopPyAdapter import (
    NetlistClosedLoopPyAdapter, ClosedLoopPortResponse, ClosedLoopTrial, _readonly,
)


class CppClosedLoopAdapter(NetlistClosedLoopPyAdapter):
    backend_name = "CRIMSON C++ native subsection (validation only)"
    _uses_controlled_lifecycle = False

    def __init__(self, *args, worker_executable=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.worker_executable = worker_executable or (
            Path(__file__).resolve().parents[1] / "ext/build/crimson_closed_loop_validation_worker")
        self._native = None
        self._native_timestep = None

    def load(self, dt=None):
        super().load(dt)
        if self._native is None:
            native = CrimsonNetlistWorkerClient(self.worker_executable)
            try:
                native.start()
                native._send("LOAD {} {:.17g} {}".format(_quote_worker_argument(self._normalized_directory),
                    self.delt, len(self.surface_ids)), "STARFISH_OK LOAD")
                published = self._read_snapshot(native._send("SNAPSHOT", "STARFISH_OK SNAPSHOT"))
            except Exception:
                native.abort()
                raise
            self._native = native
            self._published = published
            self._history = {owner: [self._physical_values(owner, published)] for owner in self._observations}
        return self

    def start_timestep(self, timestep, time, dt):
        super().start_timestep(timestep, time, dt)
        if self._native_timestep != timestep:
            self._native._send("START {}".format(timestep), "STARFISH_OK START")
            self._native_timestep = timestep

    def _read_snapshot(self, line):
        fields = line.split()[2:]
        published = self._published.copy()
        offset = 0
        for observation in self._observations.values():
            for indices in (observation.pressure_indices, observation.flow_indices, observation.volume_indices):
                count = int(fields[offset])
                offset += 1
                if count != len(indices):
                    raise RuntimeError("C++ physical observation count differs from parsed topology")
                published[indices] = [float(value) for value in fields[offset:offset + count]]
                offset += count
        if offset != len(fields) or not np.isfinite(published).all():
            raise RuntimeError("malformed or nonfinite C++ circuit snapshot")
        return published

    def _query(self, command, flows, pressures):
        count = len(self.surface_ids)
        flows, pressures = (np.asarray(x, dtype=np.float64) for x in (flows, pressures))
        if any(x.shape != (count,) or not np.isfinite(x).all() for x in (flows, pressures)):
            raise ValueError("C++ requires finite complete port vectors")
        payload = " ".join(format(float(x), ".17g") for x in np.r_[flows, pressures])
        prefix = "STARFISH_OK QUERY" if command == "QUERY" else "STARFISH_OK SNAPSHOT"
        line = self._native._send(command + " " + payload, prefix)
        if command == "TRIAL":
            return self._read_snapshot(line)
        values = np.asarray([float(x) for x in line.split()[2:]], dtype=np.float64)
        if values.shape != (3 * count,) or not np.isfinite(values).all():
            raise RuntimeError("malformed C++ interface response")
        values = values.reshape(count, 3)
        if not np.isin(values[:, 0], [0., 1.]).all():
            raise RuntimeError("invalid C++ interface modes")
        return values[:, 0].astype(bool), values[:, 1], values[:, 2]

    def probe_port_response(self, timestep, time, dt, flows, pressures):
        self.start_timestep(timestep, time, dt)
        flows, pressures = np.asarray(flows, dtype=np.float64), np.asarray(pressures, dtype=np.float64)
        modes, base_p, base_q = self._query("QUERY", flows, pressures)
        count = len(modes)
        hp, hq = np.empty((count, count)), np.empty((count, count))
        for column, flow_mode in enumerate(modes):
            probe_q, probe_p = flows.copy(), pressures.copy()
            (probe_q if flow_mode else probe_p)[column] += 1.0
            probe_modes, p, q = self._query("QUERY", probe_q, probe_p)
            if not np.array_equal(probe_modes, modes):
                raise RuntimeError("native probe changed the frozen interface modes")
            hp[:, column], hq[:, column] = p - base_p, q - base_q
        inputs = np.where(modes, flows, pressures)
        return ClosedLoopPortResponse(self._source, timestep, tuple(self.surface_ids), _readonly(modes),
            _readonly(hp), _readonly(hq), _readonly(base_p - hp @ inputs), _readonly(base_q - hq @ inputs))

    def solve_trial(self, timestep, time, dt, flows, pressures):
        self.start_timestep(timestep, time, dt)
        published = self._query("TRIAL", flows, pressures)
        candidate = SimpleNamespace(current=SimpleNamespace(source_accepted_steps=self._state.accepted_steps))
        ports = self.model.ports
        return ClosedLoopTrial(self._source, timestep, candidate, _readonly(published),
            _readonly(published[ports.interface_pressure_indices]),
            _readonly(published[ports.interface_flow_indices] * ports.interface_flow_signs))

    def finalize_timestep(self, timestep):
        if timestep == self._last_finalized:
            return
        if self._closed or self._trial is None or timestep != self._active_timestep:
            raise RuntimeError("native acceptance requires a current complete trial")
        self.stage_trial(self._trial)
        self._native._send("ACCEPT", "STARFISH_OK ACCEPT")
        published = self._trial.published
        self._state = self._state._replace(
            history_values=published[self.model.history.current_solution_columns].copy(),
            accepted_steps=np.int64(self._state.accepted_steps + 1))
        self._published = published.copy()
        for owner in self._history:
            self._history[owner].append(self._physical_values(owner, published))
        self._trial = None
        self._active_timestep = None
        self._last_finalized = timestep

    def close(self):
        try:
            if self._native is not None:
                self._native.close()
                self._native = None
        finally:
            super().close()
