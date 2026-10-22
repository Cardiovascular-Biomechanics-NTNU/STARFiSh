"""Compare 1D lifecycle transitions directly with the upstream NumPy driver."""

import copy
from contextlib import redirect_stdout
import importlib
import io
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import h5py
import numpy as np

from NetworkLib.netlistDriver import OneDDriver
from UtilityLib.netlistPyAdapter import NetlistPyAdapter, _reference_modules
from UtilityLib.netlistClosedLoopPyAdapter import NetlistClosedLoopPyAdapter

ROOT = Path(__file__).resolve().parents[1]


def assert_tree_equal(test, expected, actual):
    if isinstance(expected, dict):
        test.assertEqual(set(expected), set(actual))
        for key in expected:
            assert_tree_equal(test, expected[key], actual[key])
    elif isinstance(expected, (tuple, list)):
        test.assertEqual(type(expected), type(actual))
        test.assertEqual(len(expected), len(actual))
        for left, right in zip(expected, actual):
            assert_tree_equal(test, left, right)
    else:
        np.testing.assert_array_equal(expected, actual)


class DriverChecks(unittest.TestCase):
    def test_event_order_repeated_trials_and_single_acceptance(self):
        events = []
        manager = SimpleNamespace(
            start_timestep=lambda n, time, dt: events.append(('init', n, time, dt)),
            finalize_timestep=lambda n: events.append(('accept', n)))
        driver = OneDDriver(manager, .1)
        for n in range(3):
            context = driver.iter_init(n, n*.1, .1)
            self.assertAlmostEqual(context.end_time, (n+1)*.1)
            with self.assertRaises(RuntimeError):
                driver.iter_init(n, n*.1, .1)
            for _ in range(3):
                driver.iter_step(lambda: events.append(('trial', n)))
                self.assertEqual(driver.accepted_steps, n)
            driver.iter_finalize()
            events.append(('output', n))
            with self.assertRaises(RuntimeError):
                driver.iter_finalize()
        self.assertEqual([x[0] for x in events], ['init', 'trial', 'trial', 'trial', 'accept', 'output']*3)

    def test_failed_domain_or_initialization_cannot_accept_or_retry(self):
        for fail_init in (False, True):
            def fail(*args):
                raise ValueError('intentional failure')
            accepted = []
            manager = SimpleNamespace(start_timestep=fail if fail_init else lambda *args: None,
                                      finalize_timestep=lambda n: accepted.append(n))
            driver = OneDDriver(manager, .1)
            with self.assertRaises(ValueError):
                driver.iter_init(0, 0., .1)
                driver.iter_step(fail)
            with self.assertRaises(RuntimeError):
                driver.iter_finalize()
            with self.assertRaises(RuntimeError):
                driver.iter_init(0, 0., .1)
            self.assertEqual(accepted, [])

    def test_clock_and_step_guards(self):
        manager = SimpleNamespace(start_timestep=lambda *args: None, finalize_timestep=lambda n: None)
        driver = OneDDriver(manager, .1)
        for args in ((0, .1, .1), (0, 0., .2), (-1, -.1, .1)):
            with self.assertRaises(ValueError):
                driver.iter_init(*args)
        with self.assertRaises(RuntimeError):
            driver.iter_init(1, .1, .1)
        driver.iter_init(0, 0., .1)
        with self.assertRaises(RuntimeError):
            driver.iter_finalize()


class UpstreamIdentityChecks(unittest.TestCase):
    def test_regular_controller_matches_zero_d_driver_first_and_every_step(self):
        adapter = NetlistPyAdapter(ROOT/'ext/tests/controllers/netlist_surfaces.xml', delt=.001, surface_ids=[0])
        self.addCleanup(adapter.close)
        adapter.load()
        api = adapter._api
        circuit, _ = api['NetlistXmlReader'].parse_netlist_circuit_with_controls(
            adapter.netlist_xml, 1, implementation='reference')
        mapping = api['NetlistCircuit_reference'].get_dof_map(circuit)
        manager = api['BoundaryConditionManager_reference'].BoundaryConditionManager()
        bc = manager.add_netlist_bc(0, circuit, mapping, .001, delt=.001)
        controls = importlib.import_module('ControlSystemsManager_reference')
        protocol = importlib.import_module('ControllerProtocol_reference')
        driver_api = importlib.import_module('pureZeroDDriver_reference')
        n = [0]

        def inputs(driver):
            # The fixture has no history slots; both current pressures still
            # belong in its controller observations, including the initial row.
            p = np.array([1000., 0.]) if bc.last_solution is None else np.array([
                bc.last_solution[mapping['pressure_node_idx'][key]] for key in sorted(circuit.nodes)])
            q = np.array([0.]) if bc.last_solution is None else np.array([bc.boundary_flow])
            return protocol.ControllerInputs(np.float64(.001), np.float64(n[0]*.001),
                p, q, np.zeros(0), np.zeros(1), {})

        def apply(driver, schedule, step):
            return controls.apply_controller_targets_by_boundary(schedule, step,
                {0: controls.AppliedControllerTargets(bc.component_parameter_values,
                    bc.volume_unstressed_values, bc.prescribed_flow_values, bc.prescribed_pressure_values)})

        reference = driver_api.ZeroDDriver(total_cols=0, layout=None, dof_map=mapping,
            initial_history_p=np.zeros(0), initial_history_f=np.zeros(0), initial_history_v=np.zeros(0),
            alfi_delt=.001, delt=.001, bc_manager=manager, circuit_data=circuit,
            control_systems_manager=(adapter._schedule, copy.deepcopy(adapter._controller_state)),
            controller_inputs_factory=inputs, controller_target_applier=apply)
        for index in range(10):
            n[0] = index
            reference.iter_init()
            adapter.start_timestep(index, index*.001, .001)
            assert_tree_equal(self, reference.control_systems_manager[1], adapter._controller_state)
            self.assertEqual(adapter._controller_state.current_timestep_index, index+1)
            self.assertEqual(adapter._bcs[0].component_parameter_values[0], 100.*2**(index+1))
            for q in (1e-5, -2e-5, 3e-5):
                reference.interface_flows[0] = q
                reference.iter_step()
                data = adapter.compute_interface_data(0, index, (index+1)*.001, .001, q)
                self.assertEqual(data[2], bc.get_dp_dq())
                self.assertEqual(data[3], bc.get_Hop())
            expected = reference.iter_finalize()
            adapter.update_state_all_and_finalize(index, (index+1)*.001, .001,
                [(0, data[2]*q+data[3], q)])
            np.testing.assert_array_equal(expected, adapter._bcs[0].last_solution)
            assert_tree_equal(self, reference.control_systems_manager[1], adapter._controller_state)

    def test_regular_refreshes_actual_target_and_runs_once_before_probes(self):
        adapter = NetlistPyAdapter(ROOT/'ext/tests/controllers/netlist_surfaces.xml', delt=.001, surface_ids=[0])
        self.addCleanup(adapter.close)
        adapter.load()
        adapter._bcs[0].set_component_parameter_values(np.array([123.]))
        for q in (1e-5, 2e-5, -1e-5):
            self.assertEqual(adapter.compute_interface_data(0, 0, .001, .001, q)[2], 246.)
            self.assertEqual(adapter._controller_state.current_timestep_index, 1)
        self.assertEqual(len(adapter._history[0]), 1)

    def test_regular_feedback_and_capacitor_history_match_upstream(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'netlist_surfaces.xml'
            tree = ET.parse(ROOT/'examples/baseline_netlist_wk3/netlist_surfaces.xml')
            control = ET.SubElement(tree.find('./circuit/components/component'), 'control')
            ET.SubElement(control, 'type').text = 'customPython'
            ET.SubElement(control, 'source').text = 'feedback'
            tree.write(path)
            (Path(folder)/'feedback_reference.py').write_text('''import numpy as np
from ControllerProtocol_reference import ControllerProgram, ControllerResult
CONTROLLER_API_VERSION = "1"
CONTROLLER_PRIORITY = 0
def build_controller_program():
    def initialize():
        return np.float64(2e7), np.int64(0)
    def update(parameters, state, inputs):
        target = parameters + 10.*inputs.pressure[0] + 1e10*inputs.flow[0] + 1e6*inputs.time
        return ControllerResult(np.asarray([target]), state+1, {})
    return ControllerProgram("feedback", 1, initialize, update, {})
''')
            adapter = NetlistPyAdapter(path, delt=.001, surface_ids=[0])
            self.addCleanup(adapter.close)
            adapter.load()
            circuit, _ = adapter._api['NetlistXmlReader'].parse_netlist_circuit_with_controls(path, 1, implementation='reference')
            mapping = adapter._api['NetlistCircuit_reference'].get_dof_map(circuit)
            manager = adapter._api['BoundaryConditionManager_reference'].BoundaryConditionManager()
            bc = manager.add_netlist_bc(0, circuit, mapping, .001, delt=.001)
            controls = importlib.import_module('ControlSystemsManager_reference')
            protocol = importlib.import_module('ControllerProtocol_reference')
            api = importlib.import_module('pureZeroDDriver_reference')
            published = [np.array([circuit.nodes[i].initial_pressure for i in sorted(circuit.nodes)]),
                         np.zeros(len(circuit.components)), np.zeros(0)]
            n = [0]

            def inputs(driver):
                return protocol.ControllerInputs(np.float64(.001), np.float64(n[0]*.001),
                                                  *published, np.zeros(1), {})

            def apply(driver, schedule, step):
                return controls.apply_controller_targets_by_boundary(schedule, step,
                    {0: controls.AppliedControllerTargets(bc.component_parameter_values, bc.volume_unstressed_values,
                                                          bc.prescribed_flow_values, bc.prescribed_pressure_values)})

            hp, hf, hv = bc.get_accepted_history_state()
            reference = api.ZeroDDriver(total_cols=0, layout=None, dof_map=mapping,
                initial_history_p=hp, initial_history_f=hf, initial_history_v=hv,
                alfi_delt=.001, delt=.001, bc_manager=manager, circuit_data=circuit,
                control_systems_manager=(adapter._schedule, copy.deepcopy(adapter._controller_state)),
                controller_inputs_factory=inputs, controller_target_applier=apply)
            for index in range(24):
                n[0] = index
                reference.iter_init()
                adapter.start_timestep(index, index*.001, .001)
                np.testing.assert_array_equal(bc.component_parameter_values, adapter._bcs[0].component_parameter_values)
                for q in (1e-5, -1e-5, (1.+.25*np.sin(index))*1e-5):
                    reference.interface_flows[0] = q
                    reference.iter_step()
                    data = adapter.compute_interface_data(0, index, (index+1)*.001, .001, q)
                    np.testing.assert_array_equal(data[2:], [bc.get_dp_dq(), bc.get_Hop()])
                solution = reference.iter_finalize()
                adapter.update_state_all_and_finalize(index, (index+1)*.001, .001,
                                                       [(0, data[2]*q+data[3], q)])
                np.testing.assert_array_equal(solution, adapter._bcs[0].last_solution)
                assert_tree_equal(self, bc.get_accepted_history_state(), adapter._bcs[0].get_accepted_history_state())
                assert_tree_equal(self, reference.control_systems_manager[1], adapter._controller_state)
                published[0] = np.array([solution[mapping['pressure_node_idx'][i]] for i in sorted(circuit.nodes)])
                flow_start = mapping['num_pressures'] + mapping['num_history_pressures']
                published[1] = np.array([solution[flow_start+mapping['component_flow_idx'][i]] for i in sorted(circuit.components)])

    def test_closed_loop_matches_upstream_full_state_controllers_and_diodes(self):
        source, _ = _reference_modules()
        fixture = source.parent/'tests/fixtures/closed_loop_modern_controls'
        adapter = NetlistClosedLoopPyAdapter(fixture/'netlist_surfaces.xml', delt=.001, surface_ids=[5])
        self.addCleanup(adapter.close)
        adapter.load()
        reader = importlib.import_module('NetlistXmlReader')
        case = importlib.import_module('NetlistCase')
        topology = importlib.import_module('ClosedLoopDownstreamSubsection')
        protocol = importlib.import_module('ControllerProtocol_reference')
        manifest_api = importlib.import_module('ControllerManifest_reference')
        api = importlib.import_module('pureZeroDDriver_reference')
        directory = adapter._normalized_directory
        upstream, up_controls = reader.parse_netlist_circuit_with_controls(
            directory/'netlist_surfaces.xml', 1, implementation='reference')
        downstream, connections, down_controls = reader.parse_downstream_netlist_circuit_with_controls(
            directory/'netlist_closed_loop_downstream.xml', 1, directory/'netlist_surfaces.xml', (1,),
            implementation='reference')
        setup = case.prepare_closed_loop_subsection((1,), (upstream, downstream), connections, implementation='reference')
        model, published = setup['model'], setup['initial_published_solution']
        inputs = {}
        for owner in model.layout.block_names:
            observation = topology.build_closed_loop_observation_layout(model.layout, owner)
            inputs[owner] = protocol.ControllerInputs(np.float64(.001), np.float64(0.),
                published[observation.pressure_indices], published[observation.flow_indices],
                published[observation.volume_indices], np.zeros(1), {})
        manifest = manifest_api.build_closed_loop_controller_manifest(model.layout.block_names,
            setup['circuits_by_owner'], {'surface:1': up_controls, 'downstream:1': down_controls}, inputs, directory)
        schedule, controllers = manifest_api.build_control_systems_manager_from_manifest(manifest, derive_setup_broadcasts=True)
        state = api.create_controlled_closed_loop_state(model.layout, model.history, setup['initial_history_values'],
            controllers, setup['initial_targets'], published, diode_model=model)
        modes = set()
        for n in range(40):
            before = copy.deepcopy(adapter._controlled_state)
            prepared = api.controlled_closed_loop_iter_init(model.layout, model.history,
                setup['circuits_by_owner'], schedule, state, np.float64(.001), diode_model=model)
            q, p = np.array([1. if n%4 < 2 else -1.]), np.array([100. if n%4 < 2 else -100.])
            expected = api.controlled_closed_loop_iter_step(model.layout, model.history, prepared,
                setup['assemble_blocks'], {'flows': q, 'pressures': p}, diode_model=model)
            with patch.object(api, 'controlled_closed_loop_iter_init', wraps=api.controlled_closed_loop_iter_init) as init:
                for _ in range(3):
                    response = adapter.probe_port_response(n, (n+1)*.001, .001, q, p)
                    modes.add(bool(response.flow_input_mask[0]))
                trial = adapter.solve_trial(n, (n+1)*.001, .001, q, p)
                self.assertEqual(init.call_count, 1)
            assert_tree_equal(self, before, adapter._controlled_state)
            assert_tree_equal(self, prepared, adapter._prepared)
            assert_tree_equal(self, expected, trial.candidate)
            # Producer reads downstream p/V; consumer sees its broadcast in
            # this update, before any circuit solve changes observations.
            self.assertEqual(prepared.controller_step.gathered_broadcasts['down_p'],
                state.published_solution[model.layout.column_labels.index('downstream:1/pressure:1')])
            state = api.controlled_closed_loop_iter_finalize(model.layout, model.history,
                setup['circuits_by_owner'], state, expected, diode_model=model)
            adapter.stage_trial(trial)
            adapter.update_state_all_and_finalize(n, (n+1)*.001, .001, [(5, trial.pressures[0], trial.flows[0])])
            assert_tree_equal(self, state, adapter._controlled_state)
            self.assertEqual(int(state.controllers.current_timestep_index), n+1)
        self.assertEqual(modes, {False, True})

    def test_closed_failed_script_preflight_and_unaccepted_close(self):
        with tempfile.TemporaryDirectory() as folder:
            case = Path(folder)/'case'
            shutil.copytree(ROOT/'ext/tests/closed_loop_resistance', case)
            tree = ET.parse(case/'netlist_surfaces.xml')
            controls = ET.SubElement(tree.find('./circuit/components/component'), 'control')
            ET.SubElement(controls, 'type').text = 'customPython'
            ET.SubElement(controls, 'source').text = 'absent'
            tree.write(case/'netlist_surfaces.xml')
            adapter = NetlistClosedLoopPyAdapter(case/'netlist_surfaces.xml', delt=.001, surface_ids=[0,4])
            self.addCleanup(adapter.close)
            with self.assertRaises(FileNotFoundError):
                adapter.load()
            self.assertIsNone(adapter._setup)

    def test_failed_controller_preparation_cannot_be_retried(self):
        adapters = [NetlistPyAdapter(ROOT/'ext/tests/controllers/netlist_surfaces.xml', delt=.001, surface_ids=[0]),
            NetlistClosedLoopPyAdapter(ROOT/'ext/tests/closed_loop_controlled/netlist_surfaces.xml',
                                      delt=.001, surface_ids=[0,4])]
        for adapter in adapters:
            self.addCleanup(adapter.close)
            adapter.load()
            module, name = ((adapter, '_update_controllers') if isinstance(adapter, NetlistPyAdapter)
                            else (adapter._driver_api, 'controlled_closed_loop_iter_init'))
            with patch.object(module, name, side_effect=ValueError('invalid target')):
                with self.assertRaises(ValueError):
                    adapter.start_timestep(0, 0., .001)
            with self.assertRaises(RuntimeError):
                adapter.start_timestep(0, 0., .001)
            self.assertTrue(all(len(rows) == 1 for rows in adapter._history.values()))


class FullDomainLifecycleChecks(unittest.TestCase):
    def test_regular_and_closed_controllers_prepare_before_domain_accept_before_output(self):
        import solver
        import SolverLib.class1DflowSolver as flow_module
        from NetworkLib.netlistManager import get_default_netlist_manager
        original = flow_module.FlowSolver
        with tempfile.TemporaryDirectory() as folder:
            for closed in (False, True):
                case = Path(folder)/('closed' if closed else 'regular')
                shutil.copytree(ROOT/'ext/tests/closed_loop_controlled', case)
                if not closed:
                    (case/'netlist_closed_loop_downstream.xml').unlink()
                    tree = ET.parse(case/'netlist_surfaces.xml')
                    for node in tree.findall('./circuit/nodes/node'):
                        if node.findtext('index') == '2':
                            ET.SubElement(node, 'prescribedPressureType').text = 'fixed'
                    tree.write(case/'netlist_surfaces.xml')
                    (case/'portResistance_reference.py').write_text('''import numpy as np
from ControllerProtocol_reference import ControllerProgram, ControllerResult
CONTROLLER_API_VERSION = "1"
CONTROLLER_PRIORITY = 0
def build_controller_program():
    def initialize():
        return np.float64(1e7), np.int64(0)
    def update(parameters, state, inputs):
        return ControllerResult(np.asarray([parameters*(1.+.01*(state+1))]), state+1, {})
    return ControllerProgram("ramp", 1, initialize, update, {})
''')
                observations = []

                def construct(*args, **kwargs):
                    instance = original(*args, **kwargs)
                    publication = instance.vascularNetwork

                    def before_domain():
                        adapter = get_default_netlist_manager().adapter
                        n = instance.currentTimeStep[0]
                        if closed:
                            self.assertEqual(adapter._prepared.controller_step.next_state.current_timestep_index, n+1)
                            self.assertEqual(adapter._controlled_state.controllers.current_timestep_index, n)
                        else:
                            self.assertEqual(adapter._controller_state.current_timestep_index, n+1)
                            self.assertEqual(adapter._bcs[0].component_parameter_values[0], 1e7*(1.+.01*(n+1)))
                        self.assertEqual(instance.netlistDriver.accepted_steps, n)
                        self.assertTrue(all(len(rows) == n+1 for rows in adapter._history.values()))
                        observations.append(('domain', n))

                    def after_accept():
                        manager = get_default_netlist_manager()
                        n = instance.currentTimeStep[0]
                        self.assertEqual(manager.pending_states, {})
                        self.assertEqual(instance.netlistDriver.accepted_steps, n+1)
                        self.assertTrue(all(len(rows) == n+2 for rows in manager.adapter._history.values()))
                        if closed:
                            self.assertEqual(manager.adapter._controlled_state.controllers.current_timestep_index, n+1)
                        observations.append(('output', n))
                        publication()

                    instance.domainNumericalObjects.insert(0, before_domain)
                    instance.numericalObjects = [after_accept if obj is publication else obj for obj in instance.numericalObjects]
                    return instance

                with patch.object(flow_module, 'FlowSolver', construct), redirect_stdout(io.StringIO()):
                    output, _, _ = solver.run_case(str(case/'input.xml'), str(case/'results'),
                                                   'solution', '001', 'lifecycle order')
                self.assertTrue(observations)
                self.assertEqual([event for event, _ in observations], ['domain', 'output']*(len(observations)//2))
                directory = Path(output).parent
                p = np.loadtxt(directory/'netlistPressures_surface_0.dat')
                q = np.loadtxt(directory/'netlistFlows_surface_0.dat')
                self.assertEqual(len(p), len(observations)//2+1)
                with h5py.File(output) as data:
                    vessel = next(iter(data['vessels'].values()))
                    np.testing.assert_allclose(vessel['Psol'][:,0], p[:,1], rtol=5e-11, atol=1e-8)
                    np.testing.assert_allclose(-vessel['Qsol'][:,0], q[:,1], rtol=5e-11, atol=1e-12)


if __name__ == '__main__':
    unittest.main()
