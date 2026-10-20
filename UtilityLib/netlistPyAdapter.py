"""STARFiSh adapter for the standalone CRIMSON NumPy netlist implementation.

The circuit equations live in netlist_py, located by ../netlist_config.py.
This module owns STARFiSh surface bindings, timestep acceptance, and output.
It imports no JAX, C++, MPI, PETSc, or Python-2 runtime.

For compatibility with STARFiSh's retained C++ worker, sorted physical surface
IDs map to XML circuitIndex 1..N and controllers run AFTER circuit acceptance.
That controller phase is intentional: netlist_py's standalone ordinary 0D
driver uses a different, pre-solve controller phase. No replacement domain is
created here. All circuit values and exchanged P/Q must use consistent SI
units (Pa, m^3/s, m^3); no implicit unit conversion is performed.
"""

from __future__ import annotations

import importlib
import logging
import math
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np


logger = logging.getLogger("starfish")


def netlist_source_directory():
    """Resolve the single user-editable location, without importing a solver."""
    import netlist_config

    directory = Path(netlist_config.NETLIST_PY_DIRECTORY).expanduser()
    if not directory.is_absolute():
        directory = Path(netlist_config.__file__).resolve().parent / directory
    directory = directory.resolve()
    if (directory / "src" / "NetlistCircuit_reference.py").is_file():
        directory /= "src"
    for filename in ("NetlistCircuit_reference.py", "BoundaryConditionManager_reference.py",
                     "NetlistXmlReader.py"):
        if not (directory / filename).is_file():
            raise FileNotFoundError(
                "netlist_config.py: NETLIST_PY_DIRECTORY must point to the "
                "netlist_py repository or src directory; missing {} in {}".format(
                    filename, directory))
    return directory


def _reference_modules():
    source = netlist_source_directory()
    # netlist_py currently ships top-level modules rather than a package.
    # Never mix a cached module from another checkout with the configured one.
    for path in source.glob("*.py"):
        existing = sys.modules.get(path.stem)
        if existing is not None and getattr(existing, "__file__", None):
            if Path(existing.__file__).resolve().parent != source:
                raise ImportError("netlist_py module {} is already loaded from {}; "
                                  "restart Python after changing netlist_config.py".format(
                                      path.stem, existing.__file__))
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    return source, {
        name: importlib.import_module(name)
        for name in ("NetlistXmlReader", "NetlistCircuit_reference",
                     "BoundaryConditionManager_reference")
    }


def _surface_ids(values):
    result = []
    for value in values:
        if isinstance(value, (bool, np.bool_)) or int(value) != value or value < 0:
            raise ValueError("netlist surface IDs must be nonnegative integers")
        result.append(int(value))
    if len(result) != len(set(result)):
        raise ValueError("duplicate netlist surface IDs")
    return sorted(result)


class NetlistPyAdapter:
    """One NumPy circuit manager per STARFiSh simulation, with fixed dt."""

    def __init__(self, netlist_xml, hstep=1, alfi=1.0, delt=None,
                 surface_ids=None, output_directory=None):
        self.netlist_xml = Path(netlist_xml).expanduser().resolve()
        self.surface_ids = _surface_ids(surface_ids or [])
        self.hstep = int(hstep)
        self.alfi = float(alfi)
        if self.hstep < 1 or not math.isfinite(self.alfi) or self.alfi <= 0:
            raise ValueError("hstep and alfi must be positive")
        self.delt = None if delt is None else float(delt)
        self.output_directory = None
        self.set_output_directory(output_directory)
        self.surface_to_circuit = {}
        self._manager = None
        self._bcs = {}
        self._history = {}
        self._pending = {}
        self._active_timestep = None
        self._last_finalized = -1
        self._closed = False
        self._failed = False
        self._schedule = None
        self._controller_state = None

    def set_output_directory(self, output_directory):
        self.output_directory = (None if output_directory is None else
                                 Path(output_directory).expanduser().resolve())

    def register_surfaces(self, surface_ids):
        merged = sorted(set(self.surface_ids).union(_surface_ids(surface_ids)))
        if self._manager is not None and merged != self.surface_ids:
            raise RuntimeError("cannot add netlist surfaces after loading")
        self.surface_ids = merged

    def _resolve_dt(self, dt=None):
        value = self.delt if dt is None else float(dt)
        if value is None or not math.isfinite(value) or value <= 0:
            raise ValueError("a positive finite netlist timestep dt is required")
        if self.delt is not None and value != self.delt:
            raise ValueError("netlist_py uses fixed dt={}; received {}".format(self.delt, value))
        return value

    def load(self, dt=None):
        if self._closed:
            raise RuntimeError("a closed netlist adapter cannot be reused")
        resolved_dt = self._resolve_dt(dt)
        if self._manager is not None:
            return self
        if not self.surface_ids:
            raise ValueError("register at least one surface before loading netlist_py")
        root = ET.parse(self.netlist_xml).getroot()
        indices = [int(c.findtext("circuitIndex")) for c in root.findall("circuit")]
        expected = list(range(1, len(self.surface_ids) + 1))
        if root.tag != "netlistCircuits" or sorted(indices) != expected:
            raise ValueError("registered surfaces {} require XML circuitIndex values {} "
                             "exactly; found {}".format(self.surface_ids, expected, indices))
        downstream = self.netlist_xml.with_name("netlist_closed_loop_downstream.xml")
        if downstream.is_file() and ET.parse(downstream).getroot().find("circuit") is not None:
            raise NotImplementedError("STARFiSh's scalar adapter does not yet couple "
                                      "shared downstream netlists")
        self.source_directory, self._api = _reference_modules()
        self.delt = resolved_dt
        reader = self._api["NetlistXmlReader"]
        manager = self._api["BoundaryConditionManager_reference"].BoundaryConditionManager()
        declarations = {}
        for slot, surface_id in enumerate(self.surface_ids):
            circuit, controls = reader.parse_netlist_circuit_with_controls(
                self.netlist_xml, slot + 1, implementation="reference")
            dof_map = self._api["NetlistCircuit_reference"].get_dof_map(circuit)
            bc = manager.add_netlist_bc(slot, circuit, dof_map,
                                       self.alfi * self.delt, delt=self.delt)
            self._bcs[surface_id] = bc
            self.surface_to_circuit[surface_id] = slot + 1
            declarations[surface_id] = controls
            self._history[surface_id] = [self._physical_state(bc, initial=True)]
        self._build_controllers(declarations)
        self._manager = manager
        logger.info("Netlist backend: NumPy/reference; source: %s; surface->circuit: %s",
                    self.source_directory, self.surface_to_circuit)
        return self

    def _physical_state(self, bc, initial=False):
        """Current physical columns in node/component-ID order, never history columns."""
        circuit, mapping = bc.circuit, bc.dof_map
        node_ids, component_ids = sorted(circuit.nodes), sorted(circuit.components)
        volume_ids = sorted(mapping.get("volume_idx", {}))
        if initial:
            pressure = np.asarray([circuit.nodes[i].initial_pressure for i in node_ids])
            flow = np.zeros(len(component_ids), dtype=np.float64)
            volume = np.asarray([circuit.components[i].initial_volume for i in volume_ids])
        else:
            solution = bc.last_solution
            flow_start = mapping["num_pressures"] + mapping["num_history_pressures"]
            volume_start = (flow_start + mapping["num_component_flows"]
                            + mapping["num_history_flows"])
            pressure = np.asarray([solution[mapping["pressure_node_idx"][i]] for i in node_ids])
            flow = np.asarray([solution[flow_start + mapping["component_flow_idx"][i]]
                               for i in component_ids])
            volume = np.asarray([solution[volume_start + mapping["volume_idx"][i]]
                                 for i in volume_ids])
            # C++ updateLPN hands volumes to chambers after assigning raw nodal
            # pressures; setStoredVolume publishes E*(V-V0) at the start.
            chambers = [i for i in component_ids
                        if circuit.components[i].type_name == "volumeTrackingPressureChamber"]
            for position, i in enumerate(chambers):
                component = circuit.components[i]
                elastance = bc.component_parameter_values[component_ids.index(i)]
                unstressed = bc.volume_unstressed_values[position]
                pressure[node_ids.index(component.start_node_index)] = (
                    elastance * (volume[volume_ids.index(i)] - unstressed))
        prescribed = sorted(i for i in node_ids
                            if circuit.nodes[i].prescribed_pressure_type != "notPrescribed")
        for position, i in enumerate(prescribed):
            if circuit.nodes[i].prescribed_pressure_type == "fixed":
                pressure[node_ids.index(i)] = bc.prescribed_pressure_values[position]
        result = tuple(np.asarray(values, dtype=np.float64).copy()
                       for values in (pressure, flow, volume))
        if any(not np.isfinite(values).all() for values in result):
            raise FloatingPointError("netlist_py produced nonfinite physical state")
        return result

    def _controller_inputs(self, bc, state, time):
        return self._protocol.ControllerInputs(
            np.float64(self.delt), np.float64(time), *state,
            np.zeros(1, dtype=np.float64), {})

    def _build_controllers(self, declarations):
        if not any(declarations.values()):
            return
        manifest_api = importlib.import_module("ControllerManifest_reference")
        self._control_api = importlib.import_module("ControlSystemsManager_reference")
        self._protocol = importlib.import_module("ControllerProtocol_reference")
        reader = self._api["NetlistXmlReader"]
        # Preflight every modern source before executing any controller module.
        for controls in declarations.values():
            for control in controls:
                if isinstance(control, reader.PythonControllerFile):
                    path = self.netlist_xml.parent / control.filename
                    if path.is_symlink() or not path.is_file():
                        raise FileNotFoundError("NumPy netlist control requires the modern "
                                                "case-local file {}; legacy .py scripts "
                                                "remain available for C++ reference only".format(path))
        entries, destinations = [], set()
        for surface_id, controls in declarations.items():
            bc = self._bcs[surface_id]
            inputs = self._controller_inputs(bc, self._history[surface_id][0], 0.0)
            for control in controls:
                if isinstance(control, reader.ComponentControlDeclaration):
                    builder = {
                        "bleedResistance": manifest_api.build_bleed_resistance_manifest_entry,
                        "leftVentricularElastance": manifest_api.build_left_ventricular_elastance_manifest_entry,
                    }[control.control_type]
                    entry = builder(bc.circuit, control, inputs,
                                    boundary_condition_index=bc.index)
                    if control.control_type == "leftVentricularElastance":
                        # ParameterController.hxx's constructor assigns E(0)
                        # immediately, before the first coefficient probe.
                        # Reuse the reference initializer, without advancing it.
                        parameters = importlib.import_module("ParameterController_reference")
                        initial = parameters.initialize_left_ventricular_elastance().target_value
                        value = np.asarray([initial], dtype=np.float64)
                        entry = entry._replace(initial_target_values=value,
                            setup_inputs=entry.setup_inputs._replace(current_target_values=value))
                        values = bc.component_parameter_values.copy()
                        values[entry.target_binding.target.runtime_parameter_array_index] = initial
                        bc.set_component_parameter_values(values)
                else:
                    kind = ("fixed_pressure" if control.owner_kind == "node" else
                            "unstressed_volume" if control.control_type.casefold() ==
                            "custompythonunstressedvolume" else "component_parameter")
                    item = (bc.circuit.nodes if kind == "fixed_pressure" else
                            bc.circuit.components)[control.owner_index]
                    initial = (item.initial_pressure if kind == "fixed_pressure" else
                               item.initial_unstressed_volume if kind == "unstressed_volume"
                               else item.parameter_value)
                    entry = manifest_api.build_user_controller_manifest_entry(
                        bc.circuit, self.netlist_xml.parent / control.filename,
                        kind, control.owner_index, inputs, initial,
                        boundary_condition_index=bc.index)
                binding = entry.target_binding
                destination = (bc.index, binding.target_kind, binding.target)
                if destination in destinations:
                    raise ValueError("multiple controllers cannot write the same netlist target")
                destinations.add(destination)
                entry = entry._replace(program=entry.program._replace(
                    name="surface_{}__{}".format(surface_id, entry.program.name)))
                entries.append(entry)
        manifest = manifest_api.build_controller_manifest(tuple(entries))
        self._schedule, self._controller_state = (
            manifest_api.build_control_systems_manager_from_manifest(
                manifest, derive_setup_broadcasts=True))

    def _update_controllers(self, time):
        if self._schedule is None:
            return
        by_slot = {bc.index: (surface_id, bc) for surface_id, bc in self._bcs.items()}
        inputs = {}
        for spec in (*self._schedule.python_controllers, *self._schedule.non_python_controllers):
            surface_id, bc = by_slot[spec.target_binding.boundary_condition_index]
            inputs[spec.name] = self._controller_inputs(bc, self._history[surface_id][-1], time)
        proposed = self._control_api.update_boundary_condition_control_systems(
            self._schedule, self._controller_state, inputs)
        arrays = {bc.index: self._control_api.AppliedControllerTargets(
            bc.component_parameter_values, bc.volume_unstressed_values,
            bc.prescribed_flow_values, bc.prescribed_pressure_values)
            for bc in self._bcs.values()}
        applied = self._control_api.apply_controller_targets_by_boundary(
            self._schedule, proposed, arrays)
        self._manager.refresh_after_controller_update(applied)
        self._controller_state = proposed.next_state

    def start_timestep(self, timestep, time, dt):
        self.load(dt)
        if self._failed:
            raise RuntimeError("netlist controller update failed; close this simulation")
        if type(timestep) is not int or timestep < 0 or not math.isfinite(time) or time < 0:
            raise ValueError("invalid netlist timestep or time")
        if self._active_timestep == timestep:
            return
        if self._active_timestep is not None or timestep != self._last_finalized + 1:
            raise RuntimeError("netlist timesteps must start and finalize consecutively once")
        self._manager.initialise_lpn_at_start_of_timestep_netlist()
        self._active_timestep = timestep

    def start_timestep_and_status(self, timestep, time, dt):
        self.start_timestep(timestep, time, dt)
        return {surface: (self.flow_permitted(surface),
                          self.boundary_condition_type_changed(surface))
                for surface in self.surface_ids}

    def compute_interface_data(self, surface_id, timestep, time, dt, flow):
        self.start_timestep(int(timestep), float(time), dt)
        if not math.isfinite(flow):
            raise ValueError("interface flow must be finite")
        bc = self._bcs[int(surface_id)]
        permitted = bool(bc.flow_permitted_across_3d_interface)
        changed = bool(bc.interface_mode_changed)
        if not permitted:
            return False, changed, math.nan, math.nan
        bc.compute_implicit_coefficients(timestep, flow)
        coefficients = float(bc.get_dp_dq()), float(bc.get_Hop())
        if not all(math.isfinite(value) for value in coefficients):
            raise FloatingPointError("nonfinite netlist affine coefficients")
        return (True, changed, *coefficients)

    def compute_implicit_coefficients(self, surface_id, timestep, time, dt, flow):
        return self.compute_interface_data(surface_id, timestep, time, dt, flow)[2:]

    def compute_update_coefficients(self, surface_id, timestep, time, dt, flow):
        self.start_timestep(int(timestep), float(time), dt)
        bc = self._bcs[int(surface_id)]
        if not math.isfinite(flow):
            raise ValueError("interface flow must be finite")
        bc.last_flow_bc = flow
        bc.compute_implicit_coeff_update(timestep)
        return float(bc.dp_dq_n1), float(bc.Hop_n1)

    def flow_permitted(self, surface_id, dt=None):
        self.load(dt)
        return bool(self._bcs[int(surface_id)].flow_permitted_across_3d_interface)

    def boundary_condition_type_changed(self, surface_id, dt=None):
        self.load(dt)
        return bool(self._bcs[int(surface_id)].interface_mode_changed)

    def update_state(self, surface_id, timestep, time, dt, pressure, flow):
        self.start_timestep(int(timestep), float(time), dt)
        surface_id = int(surface_id)
        if surface_id not in self._bcs:
            raise KeyError(surface_id)
        if not math.isfinite(pressure) or not math.isfinite(flow):
            raise ValueError("accepted interface pressure and flow must be finite")
        self._pending[surface_id] = (float(pressure), float(flow))

    def update_state_all_and_finalize(self, timestep, time, dt, surface_states):
        states = list(surface_states)
        if len(states) != len(self.surface_ids) or {s[0] for s in states} != set(self.surface_ids):
            raise ValueError("provide exactly one final pressure/flow state for every surface")
        # Validate the complete payload before staging any state.
        if any(not math.isfinite(value) for _, p, q in states for value in (p, q)):
            raise ValueError("accepted interface pressure and flow must be finite")
        for surface_id, pressure, flow in states:
            self.update_state(surface_id, timestep, time, dt, pressure, flow)
        self.finalize_timestep(timestep, time=time)

    def finalize_timestep(self, timestep, time=None):
        if timestep == self._last_finalized:
            return
        if self._active_timestep != timestep or set(self._pending) != set(self.surface_ids):
            raise RuntimeError("cannot finalize without current accepted states for every surface")
        pressures = np.asarray([self._pending[s][0] for s in self.surface_ids])
        flows = np.asarray([self._pending[s][1] for s in self.surface_ids])
        self._manager.update_all_netlist_lpns(timestep, flows, pressures)
        current = {}
        for surface_id, bc in self._bcs.items():
            state = self._physical_state(bc)
            if not bc.is_flow_prescribed():
                returned_flow = float(bc.flow_sign * bc.boundary_flow)
                if not np.isclose(returned_flow, self._pending[surface_id][1], atol=1e-14, rtol=1e-9):
                    raise NotImplementedError("pressure-mode port returns nonzero flow; "
                                              "this STARFiSh path supports diode-blocked zero flow")
            # Match C++ physical publication before history and diode acceptance.
            for node_id, pressure in zip(sorted(bc.circuit.nodes), state[0]):
                bc.last_solution[bc.dof_map["pressure_node_idx"][node_id]] = pressure
            current[surface_id] = state
        self._manager.finalize_lpn_at_end_of_timestep_netlists()
        for surface_id, state in current.items():
            self._history[surface_id].append(state)
        self._pending.clear()
        self._last_finalized = timestep
        self._active_timestep = None
        try:
            self._update_controllers((timestep + 1) * self.delt if time is None else time)
        except Exception:
            self._failed = True
            raise

    def close(self):
        """Write initial plus accepted states; never accept a pending trial."""
        if self._closed:
            return
        if self.output_directory is not None and self._manager is not None:
            directory = self.output_directory
            targets = [(directory / "netlist{}_surface_{}.dat".format(quantity, surface),
                        surface, axis)
                       for surface in self.surface_ids
                       for axis, quantity in enumerate(("Pressures", "Flows", "Volumes"))]
            existing = [str(path) for path, _, _ in targets if path.exists()]
            if existing:
                raise FileExistsError("netlist history targets already exist: {}".format(existing))
            directory.mkdir(parents=True, exist_ok=True)
            for path, surface, axis in targets:
                values = np.stack([state[axis] for state in self._history[surface]])
                rows = np.column_stack((np.arange(len(values)), values))
                # Keep physical surface 0; netlist_py's generic writer currently
                # rejects that label. Same .dat columns/precision, host IO only.
                with path.open("x") as output:
                    np.savetxt(output, rows, fmt=["%d"] + ["%.15g"] * values.shape[1])
        self._closed = True
