"""NumPy/reference shared-return circuits for simultaneous Starfish coupling.

Uses the configured standalone netlist-py controlled subsection lifecycle.
Starfish supplies the 1D characteristics in place of the generated 0D domain;
the upstream prepare/probe/update/finalize functions own circuit transitions.
"""

from dataclasses import dataclass
import hashlib
import importlib
import json
import logging
import math
from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET

import numpy as np

from UtilityLib.netlistPyAdapter import _reference_modules, _surface_ids

logger = logging.getLogger("starfish")


def downstream_file(netlist_xml):
    """Return a validated nonempty downstream file, or None for ordinary cases."""
    path = Path(netlist_xml).with_name("netlist_closed_loop_downstream.xml")
    if not path.exists():
        return None
    root = ET.parse(path).getroot()
    if root.tag != "netlistCircuits":
        raise ValueError("downstream XML requires a netlistCircuits root")
    return path if root.findall("circuit") else None


def _readonly(values):
    result = np.array(values, copy=True)
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class ClosedLoopPortResponse:
    source: object
    timestep: int
    surface_ids: tuple
    flow_input_mask: np.ndarray
    pressure_response: np.ndarray
    flow_response: np.ndarray
    pressure_offset: np.ndarray
    flow_offset: np.ndarray


@dataclass(frozen=True)
class ClosedLoopTrial:
    source: object
    timestep: int
    candidate: object
    published: np.ndarray
    pressures: np.ndarray
    flows: np.ndarray


class NetlistClosedLoopPyAdapter:
    """One accepted state for all attached surfaces and their return circuit."""

    backend_name = "NumPy/reference"
    _uses_controlled_lifecycle = True

    def __init__(self, netlist_xml, hstep=1, alfi=1.0, delt=None,
                 surface_ids=None, output_directory=None):
        if hstep != 1 or alfi != 1.0:
            raise NotImplementedError("Starfish closed loop currently requires hstep=1 and alfi=1")
        self.netlist_xml = Path(netlist_xml).expanduser().resolve()
        self.surface_ids = _surface_ids(surface_ids or [])
        self.delt = None if delt is None else float(delt)
        self.set_output_directory(output_directory)
        self._setup = None
        self._workspace = None
        self._closed = False
        self._active_timestep = None
        self._trial = None
        self._last_finalized = -1
        self._source = object()
        self._prepared = None
        self._failed = False

    def set_output_directory(self, directory):
        self.output_directory = None if directory is None else Path(directory).expanduser().resolve()

    def register_surfaces(self, values):
        surfaces = sorted(set(self.surface_ids).union(_surface_ids(values)))
        if self._setup is not None and surfaces != self.surface_ids:
            raise RuntimeError("cannot change loaded closed-loop surface bindings")
        self.surface_ids = surfaces

    def _dt(self, value=None):
        value = self.delt if value is None else float(value)
        if value is None or not math.isfinite(value) or value <= 0:
            raise ValueError("closed loop requires a positive finite fixed dt")
        if self.delt is not None and value != self.delt:
            raise ValueError("closed-loop dt cannot change during a simulation")
        return value

    def load(self, dt=None):
        if self._closed:
            raise RuntimeError("a closed adapter cannot be reused")
        value = self._dt(dt)
        if self._setup is not None:
            return self
        if not self.surface_ids:
            raise ValueError("register closed-loop surfaces before loading")
        downstream = downstream_file(self.netlist_xml)
        if downstream is None:
            raise ValueError("closed-loop adapter requires a downstream circuit")
        original_inputs = {path.name: path.read_bytes() for path in (self.netlist_xml, downstream)}
        tree = ET.ElementTree(ET.fromstring(original_inputs[downstream.name]))
        if len(tree.getroot().findall("circuit")) != 1 or int(tree.findtext("./circuit/circuitIndex", "0")) != 1:
            raise NotImplementedError("Starfish currently supports one downstream circuit with circuitIndex 1")
        upstream = ET.ElementTree(ET.fromstring(original_inputs[self.netlist_xml.name]))
        expected = list(range(1, len(self.surface_ids) + 1))
        if (upstream.getroot().tag != "netlistCircuits" or
                sorted(int(c.findtext("circuitIndex")) for c in upstream.findall("./circuit")) != expected):
            raise ValueError("closed-loop circuitIndex values must match sorted registered surfaces 1..N")
        self.source_directory, api = _reference_modules()
        self._kernel = importlib.import_module("ClosedLoopDownstreamSubsection_reference")
        topology = importlib.import_module("ClosedLoopDownstreamSubsection")
        prepare = importlib.import_module("NetlistCase").prepare_closed_loop_subsection
        self.physical_to_internal = {surface: slot + 1 for slot, surface in enumerate(self.surface_ids)}
        self.surface_to_circuit = dict(self.physical_to_internal)
        for element in tree.findall(".//upstreamCircuitSurfaceIndex"):
            physical = int(element.text)
            if physical not in self.physical_to_internal:
                raise ValueError("return circuit references unregistered surface {}".format(physical))
            element.text = str(self.physical_to_internal[physical])
        workspace = tempfile.TemporaryDirectory(prefix="starfish-closed-loop-")
        try:
            directory = Path(workspace.name)
            (directory / "netlist_surfaces.xml").write_bytes(original_inputs[self.netlist_xml.name])
            tree.write(directory / "netlist_closed_loop_downstream.xml", encoding="utf-8", xml_declaration=True)
            reader = api["NetlistXmlReader"]
            internal = tuple(self.physical_to_internal.values())
            circuits, declarations = [], {}
            for index in expected:
                circuit, controls = reader.parse_netlist_circuit_with_controls(
                    directory / "netlist_surfaces.xml", index, implementation="reference")
                circuits.append(circuit)
                declarations["surface:{}".format(index)] = controls
            return_circuit, connections, controls = reader.parse_downstream_netlist_circuit_with_controls(
                directory / "netlist_closed_loop_downstream.xml", 1,
                directory / "netlist_surfaces.xml", internal, implementation="reference")
            declarations["downstream:1"] = controls
            # Freeze all controller sources before executing any trusted code.
            for controls in declarations.values():
                for control in controls:
                    if isinstance(control, reader.PythonControllerFile):
                        filename = control.filename
                        path = self.netlist_xml.parent / filename
                        if Path(filename).name != filename or path.is_symlink() or not path.is_file():
                            raise FileNotFoundError("expected case-local regular reference controller: {}".format(filename))
                        original_inputs[filename] = path.read_bytes()
                        (directory / filename).write_bytes(original_inputs[filename])
                        if not self._uses_controlled_lifecycle:
                            legacy = self.netlist_xml.parent / (control.source_name + ".py")
                            if legacy.is_symlink() or not legacy.is_file():
                                raise FileNotFoundError("native controller validation needs paired legacy script: {}".format(legacy.name))
                            original_inputs[legacy.name] = legacy.read_bytes()
                            (directory / legacy.name).write_bytes(original_inputs[legacy.name])
            connected = {c.upstream_surface_index for c in connections}
            # Independent square blocks (e.g. a physical hemorrhage drain)
            # share the 1D characteristic solve and controller manager, but
            # must not receive artificial junctions into the venous return.
            self.connected_surface_ids = [surface for surface in self.surface_ids
                                          if self.physical_to_internal[surface] in connected]
            self.independent_surface_ids = [surface for surface in self.surface_ids
                                            if self.physical_to_internal[surface] not in connected]
            setup = prepare(internal, (*circuits, return_circuit), connections, implementation="reference")
            model = setup["model"]
            observations = {owner: topology.build_closed_loop_observation_layout(model.layout, owner)
                            for owner in model.layout.block_names}
            published = np.array(setup["initial_published_solution"], copy=True)
            protocol = importlib.import_module("ControllerProtocol_reference")
            manifest_api = importlib.import_module("ControllerManifest_reference")
            driver = importlib.import_module("pureZeroDDriver_reference")
            inputs = {owner: protocol.ControllerInputs(
                np.float64(value), np.float64(0.), published[observation.pressure_indices],
                published[observation.flow_indices], published[observation.volume_indices],
                np.zeros(1, dtype=np.float64), {}) for owner, observation in observations.items()}
            manifest = manifest_api.build_closed_loop_controller_manifest(
                model.layout.block_names, setup["circuits_by_owner"], declarations, inputs, directory)
            schedule, controllers = manifest_api.build_control_systems_manager_from_manifest(
                manifest, derive_setup_broadcasts=True)
            controlled_state = driver.create_controlled_closed_loop_state(
                model.layout, model.history, setup["initial_history_values"], controllers,
                setup["initial_targets"], published, diode_model=model)
        except Exception:
            workspace.cleanup()
            raise
        self._workspace = workspace
        self._original_inputs = original_inputs
        self._normalized_directory = directory
        self._setup, self.model = setup, model
        self._driver_api, self._schedule = driver, schedule
        self._controlled_state = controlled_state
        self._state = controlled_state.accepted
        self._observations = observations
        self._published = published
        self._history = {owner: [self._physical_values(owner, published)] for owner in observations}
        self.delt = value
        logger.info("Netlist backend: %s closed-loop subsection; physical->internal: %s",
                    self.backend_name, self.physical_to_internal)
        return self

    def _physical_values(self, owner, published):
        observation = self._observations[owner]
        return tuple(np.array(published[indices], copy=True) for indices in
                     (observation.pressure_indices, observation.flow_indices, observation.volume_indices))

    def start_timestep(self, timestep, time, dt):
        self.load(dt)
        if self._failed:
            raise RuntimeError("closed-loop preparation failed; close this simulation")
        if type(timestep) is not int or timestep < 0 or not math.isfinite(time) or time < 0:
            raise ValueError("invalid closed-loop timestep/time")
        if self._active_timestep == timestep:
            return
        if self._active_timestep is not None or timestep != self._last_finalized + 1:
            raise RuntimeError("closed-loop timesteps must start and finalize consecutively")
        if self._uses_controlled_lifecycle:
            try:
                self._prepared = self._driver_api.controlled_closed_loop_iter_init(
                    self.model.layout, self.model.history, self._setup["circuits_by_owner"],
                    self._schedule, self._controlled_state, np.float64(dt), diode_model=self.model)
            except Exception:
                self._failed = True
                raise
        self._active_timestep = timestep

    def _candidate(self, timestep, time, dt, flows, pressures, stage):
        self.start_timestep(timestep, time, dt)
        count = len(self.surface_ids)
        vectors = tuple(np.asarray(x, dtype=np.float64) for x in (flows, pressures))
        if any(x.shape != (count,) or not np.isfinite(x).all() for x in vectors):
            raise ValueError("provide finite pressure and flow vectors in physical surface order")
        flows, pressures = vectors
        controlled = self._driver_api.controlled_closed_loop_iter_step(
            self.model.layout, self.model.history, self._prepared, self._setup["assemble_blocks"],
            {"flows": flows, "pressures": pressures}, stage=stage,
            effective_dt=np.float64(dt) if stage == "probe" else None, diode_model=self.model)
        return controlled

    def probe_port_response(self, timestep, time, dt, flows, pressures):
        candidate = self._candidate(timestep, time, dt, flows, pressures, "probe").diode_timestep
        response = self._kernel.compute_closed_loop_diode_interface_response(self.model, candidate)
        return ClosedLoopPortResponse(self._source, timestep, tuple(self.surface_ids),
            _readonly(candidate.flow_permitted), *(_readonly(x) for x in (
                response.pressure_response, response.flow_response,
                response.pressure_offset, response.flow_offset)))

    def solve_trial(self, timestep, time, dt, flows, pressures):
        controlled = self._candidate(timestep, time, dt, flows, pressures, "update")
        candidate = controlled.diode_timestep
        published = self._kernel.get_closed_loop_published_solution(self.model, candidate)
        for values in candidate.current:
            if isinstance(values, np.ndarray):
                values.setflags(write=False)
        ports = self.model.ports
        return ClosedLoopTrial(self._source, timestep, controlled, _readonly(published),
            _readonly(published[ports.interface_pressure_indices]),
            _readonly(published[ports.interface_flow_indices] * ports.interface_flow_signs))

    def stage_trial(self, trial):
        if trial.source is not self._source or trial.timestep != self._active_timestep:
            raise RuntimeError("cannot stage a foreign or stale closed-loop trial")
        if trial.candidate.current.source_accepted_steps != self._state.accepted_steps:
            raise RuntimeError("closed-loop trial history has already advanced")
        self._trial = trial

    def update_state_all_and_finalize(self, timestep, time, dt, surface_states):
        self.start_timestep(timestep, time, dt)
        states = list(surface_states)
        if (len(states) != len(self.surface_ids) or
                {s[0] for s in states} != set(self.surface_ids)):
            raise ValueError("provide exactly one closed-loop endpoint state per surface")
        ordered = {s[0]: s[1:] for s in states}
        p, q = np.asarray([ordered[s] for s in self.surface_ids], dtype=np.float64).T
        if not np.isfinite(p).all() or not np.isfinite(q).all():
            raise ValueError("accepted closed-loop endpoint states must be finite")
        trial = self._trial
        if trial is None:
            trial = self.solve_trial(timestep, time, dt, q, p)
        if (not np.allclose(p, trial.pressures, rtol=5e-11, atol=1e-8) or
                not np.allclose(q, trial.flows, rtol=5e-11, atol=1e-12)):
            raise ValueError("Starfish endpoint states disagree with the complete circuit trial")
        self.stage_trial(trial)
        self.finalize_timestep(timestep)

    def finalize_timestep(self, timestep):
        if self._closed:
            raise RuntimeError("cannot finalize a closed adapter")
        if timestep == self._last_finalized:
            return
        trial = self._trial
        if trial is None or timestep != self._active_timestep:
            raise RuntimeError("cannot finalize without a complete current closed-loop trial")
        self.stage_trial(trial)
        next_state = self._driver_api.controlled_closed_loop_iter_finalize(
            self.model.layout, self.model.history, self._setup["circuits_by_owner"],
            self._controlled_state, trial.candidate, diode_model=self.model)
        snapshots = {owner: self._physical_values(owner, next_state.published_solution) for owner in self._history}
        self._controlled_state = next_state
        self._state = next_state.accepted
        self._published = next_state.published_solution.copy()
        for owner, values in snapshots.items():
            self._history[owner].append(values)
        self._trial = None
        self._prepared = None
        self._active_timestep = None
        self._last_finalized = timestep

    def close(self):
        if self._closed:
            return
        try:
            if self._setup is not None and self.output_directory is not None:
                directory = self.output_directory
                owners = {"surface:{}".format(internal): "surface_{}".format(physical)
                          for physical, internal in self.physical_to_internal.items()}
                owners["downstream:1"] = "downstreamCircuit_0"
                targets = [(directory / "netlist{}_{}.dat".format(quantity, label), owner, axis)
                           for owner, label in owners.items()
                           for axis, quantity in enumerate(("Pressures", "Flows", "Volumes"))]
                snapshot = directory / "netlist_closed_loop_inputs"
                if snapshot.exists() or any(path.exists() for path, _, _ in targets):
                    raise FileExistsError("closed-loop history/snapshot targets already exist")
                directory.mkdir(parents=True, exist_ok=True)
                shutil.copytree(self._normalized_directory, snapshot)
                hashes = {}
                for name, data in self._original_inputs.items():
                    (snapshot / ("original_" + name)).write_bytes(data)
                    hashes[name] = hashlib.sha256(data).hexdigest()
                (snapshot / "bindings.json").write_text(json.dumps({
                    "backend": self.backend_name, "dt": self.delt,
                    "endpoint_bindings": getattr(self, "endpoint_bindings", []),
                    "physical_to_internal": self.physical_to_internal,
                    "port_order": self.surface_ids, "source_sha256": hashes,
                    "connected_surface_ids": self.connected_surface_ids,
                    "independent_surface_ids": self.independent_surface_ids,
                    "accepted_steps": int(self._state.accepted_steps),
                    "controller_phase": "iter_init",
                    "controller_updates": int(self._controlled_state.controllers.current_timestep_index)
                        if self._uses_controlled_lifecycle else None,
                    "downstream_xml_to_output_index": {"1": 0}}, indent=2) + "\n")
                for path, owner, axis in targets:
                    values = np.stack([state[axis] for state in self._history[owner]])
                    rows = np.column_stack((np.arange(len(values)), values))
                    with path.open("x") as output:
                        np.savetxt(output, rows, fmt=["%d"] + ["%.15g"] * values.shape[1])
        finally:
            if self._workspace is not None:
                self._workspace.cleanup()
            self._closed = True
