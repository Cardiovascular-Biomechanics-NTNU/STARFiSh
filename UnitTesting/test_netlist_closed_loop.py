"""Analytical, lifecycle, native-C++ and full 1D closed-loop checks."""

from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from NetworkLib.netlistCoupling import CharacteristicPacket, solve_characteristics
from NetworkLib.netlistInterface import solve_robin_characteristic
from NetworkLib.netlistManager import NetlistBoundaryManager, get_default_netlist_manager
from UtilityLib.netlistClosedLoopPyAdapter import NetlistClosedLoopPyAdapter

RESISTANCE = ROOT / "ext/tests/closed_loop_resistance"
PASSIVE = ROOT / "ext/tests/closed_loop_passive"
WORKER = ROOT / "ext/build/crimson_closed_loop_validation_worker"


def packets():
    return tuple(CharacteristicPacket(s, -1, 1., 0, 0, .001, p, 0., 1.,
        np.asarray([[1., -z], [1., 1.]]), 0.) for s, p, z in ((0, 29., 1.), (4, 35., 2.)))


def response(hp, hq=None, p0=(3., 3.), q0=(0., 0.)):
    return SimpleNamespace(pressure_response=np.asarray(hp),
        flow_response=np.eye(2) if hq is None else np.asarray(hq),
        pressure_offset=np.asarray(p0), flow_offset=np.asarray(q0))


class CharacteristicChecks(unittest.TestCase):
    def test_exact_shared_resistance(self):
        result = solve_characteristics(packets(), response([[10., 8.], [8., 12.]]), np.array([True, True]))
        np.testing.assert_allclose(result.flows, [1.2, 1.6], atol=1e-14)
        np.testing.assert_allclose(result.pressures, [27.8, 31.8], atol=1e-14)
        self.assertLess(result.scaled_backward_error, 1e-14)

    def test_mixed_pressure_input_returns_nonzero_flow(self):
        mixed = response([[14/3, 2/3], [0., 1.]], [[1., 0.], [-2/3, 1/12]],
                         p0=[1., 0.], q0=[0., -.25])
        result = solve_characteristics(packets(), mixed, np.array([True, False]))
        np.testing.assert_allclose(result.flows, [1.2, 1.6], atol=1e-14)
        np.testing.assert_allclose(result.pressures, [27.8, 31.8], atol=1e-14)

    def test_scalar_reduction_proximal_distal_and_signs(self):
        matrix = np.asarray([[2., 3.], [4., -5.]])
        for position in (0, -1):
            for sign in (-1., 1.):
                packet = CharacteristicPacket(0, position, sign, 0, 0, .001,
                                               30., .5, 1., matrix, .2)
                port = SimpleNamespace(pressure_response=np.array([[7.]]),
                    flow_response=np.ones((1, 1)), pressure_offset=np.array([3.]), flow_offset=np.zeros(1))
                result = solve_characteristics([packet], port, np.array([True]))
                omega = solve_robin_characteristic(position, .2, matrix, 30., .5, 7., 3., sign)
                np.testing.assert_allclose(result.increments[0], matrix @ omega, atol=1e-14)

    def test_port_permutation(self):
        original = response([[10., 8.], [8., 12.]])
        permutation = [1, 0]
        reordered = response(original.pressure_response[np.ix_(permutation, permutation)])
        result = solve_characteristics(packets()[::-1], reordered, np.array([True, True]))
        np.testing.assert_allclose(result.flows, [1.6, 1.2], atol=1e-14)

    def test_packets_copy_transform_and_reject_mixed_generations(self):
        first, second = packets()
        with self.assertRaises(ValueError):
            first.transform[0, 0] = 999.
        from dataclasses import replace
        for field, value in (("timestep", 1), ("memory_index", 1), ("dt", .002)):
            with self.assertRaises(ValueError):
                solve_characteristics([first, replace(second, **{field: value})],
                                      response([[10., 8.], [8., 12.]]), np.array([True, True]))
        with self.assertRaises(ValueError):
            solve_characteristics([first, first], response(np.eye(2)), np.array([True, True]))

    def test_singular_and_invalid_responses_fail(self):
        with self.assertRaises(np.linalg.LinAlgError):
            solve_characteristics(packets(), response([[-1., 0.], [0., -2.]]), np.array([True, True]))
        with self.assertRaises(ValueError):
            solve_characteristics(packets(), response(np.eye(2)), np.array([1, 1]))


class AdapterChecks(unittest.TestCase):
    def test_failed_second_endpoint_does_not_scatter_or_accept(self):
        from NetworkLib.netlistCoupling import ClosedLoopBoundaryGroup
        manager = NetlistBoundaryManager()
        self.addCleanup(manager.close)
        applied = []
        members = {}
        for packet in packets():
            manager.register_boundary(packet.surface_id, vessel_id=packet.surface_id, position=-1,
                netlist_file=str(RESISTANCE / 'netlist_surfaces.xml'))
            def prepare_result(p, du, omega):
                if p.surface_id == 4:
                    raise ValueError('intentional invalid second endpoint')
                return du
            members[packet.surface_id] = SimpleNamespace(
                prepare_netlist_packet=lambda surface, sign, saved=packet: saved,
                prepare_netlist_result=prepare_result,
                apply_boundary_result=lambda result: applied.append(result))
        group = ClosedLoopBoundaryGroup(manager, members, .001)
        with self.assertRaisesRegex(ValueError, 'second endpoint'):
            group()
        self.assertEqual(applied, [])
        self.assertEqual(int(group.adapter._state.accepted_steps), 0)
        self.assertEqual(manager.pending_states, {})

    def test_reference_closed_loop_imports_neither_jax_nor_cpp(self):
        code = ("import sys; from UtilityLib.netlistClosedLoopPyAdapter import NetlistClosedLoopPyAdapter; "
                "a=NetlistClosedLoopPyAdapter('ext/tests/closed_loop_resistance/netlist_surfaces.xml', "
                "delt=.001,surface_ids=[0,4]); a.load(); "
                "assert 'jax' not in sys.modules; "
                "assert 'UtilityLib.crimsonNetlistAdapter' not in sys.modules; "
                "assert 'UnitTesting.closed_loop_cpp_reference' not in sys.modules; a.close()")
        subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, check=True)

    def make_adapter(self, output=None, directory=RESISTANCE):
        adapter = NetlistClosedLoopPyAdapter(directory / "netlist_surfaces.xml",
            delt=.001, surface_ids=[4, 0], output_directory=output)
        self.addCleanup(adapter.close)
        return adapter

    def test_repeated_probes_do_not_accept_and_surface_zero_mapping(self):
        adapter = self.make_adapter()
        adapter.load()
        state = copy.deepcopy(adapter._state)
        for flow in ([1., 2.], [2., -1.], [0., 0.]):
            result = adapter.probe_port_response(0, .001, .001, flow, [3., 3.])
            np.testing.assert_allclose(result.pressure_response, [[10., 8.], [8., 12.]], atol=1e-14)
            np.testing.assert_allclose(result.pressure_offset, [3., 3.], atol=1e-14)
        self.assertEqual(adapter.physical_to_internal, {0: 1, 4: 2})
        for old, new in zip(state, adapter._state):
            np.testing.assert_array_equal(old, new)
        self.assertEqual(len(adapter._history['downstream:1']), 1)

    def test_history_and_snapshot_output_omit_unaccepted_trial(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter = self.make_adapter(folder)
            original = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in RESISTANCE.glob('*.xml')}
            adapter.update_state_all_and_finalize(0, .001, .001, [(0, 27.8, 1.2), (4, 31.8, 1.6)])
            adapter.finalize_timestep(0)
            adapter.stage_trial(adapter.solve_trial(1, .002, .001, [1., 2.], [29., 35.]))
            adapter.close()
            for name in ('surface_0', 'surface_4', 'downstreamCircuit_0'):
                rows = np.loadtxt(Path(folder) / ('netlistPressures_' + name + '.dat'), ndmin=2)
                np.testing.assert_array_equal(rows[:, 0], [0, 1])
            manifest = json.loads((Path(folder) / 'netlist_closed_loop_inputs/bindings.json').read_text())
            self.assertEqual(manifest['accepted_steps'], 1)
            self.assertEqual(original, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in RESISTANCE.glob('*.xml')})

    def test_missing_foreign_stale_and_mismatched_endpoint_states(self):
        adapter = self.make_adapter()
        trial = adapter.solve_trial(0, .001, .001, [1., 2.], [29., 35.])
        other = self.make_adapter()
        other.start_timestep(0, .001, .001)
        with self.assertRaises(RuntimeError):
            other.stage_trial(trial)
        with self.assertRaises(ValueError):
            adapter.update_state_all_and_finalize(0, .001, .001, [(0, 29., 1.)])
        with self.assertRaises(ValueError):
            adapter.update_state_all_and_finalize(0, .001, .001, [(0, 99., 1.), (4, 35., 2.)])
        self.assertEqual(int(adapter._state.accepted_steps), 0)
        adapter.update_state_all_and_finalize(0, .001, .001, [(0, 29., 1.), (4, 35., 2.)])
        with self.assertRaises(RuntimeError):
            adapter.stage_trial(trial)
        with self.assertRaises(ValueError):
            adapter.load(.002)

    def test_malformed_controls_fail_before_script_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            for source in RESISTANCE.glob('*.xml'):
                shutil.copyfile(source, Path(folder) / source.name)
            file = Path(folder) / 'netlist_surfaces.xml'
            tree = ET.parse(file)
            ET.SubElement(tree.find('./circuit/components/component'), 'control')
            tree.write(file)
            adapter = self.make_adapter(directory=Path(folder))
            with self.assertRaises((ValueError, NotImplementedError)):
                adapter.load()

    def test_monolithic_circuit_and_characteristic_system(self):
        adapter = self.make_adapter()
        native = adapter._candidate(0, .001, .001, [0., 0.], [3., 3.], 'probe').diode_timestep
        port = adapter.probe_port_response(0, .001, .001, [0., 0.], [3., 3.])
        result = solve_characteristics(packets(), port, port.flow_input_mask)
        model = adapter.model
        size = model.layout.size
        b = np.zeros((size, 2))
        b[native.prescribed_input_rhs_indices, np.arange(2)] = model.ports.interface_flow_signs
        gp = np.eye(size)[model.ports.interface_pressure_indices]
        block = np.block([[native.current.matrix, -b], [gp, np.diag([1., 2.])]])
        rhs = np.r_[native.current.rhs, [29., 35.]]
        direct = np.linalg.solve(block, rhs)
        np.testing.assert_allclose(direct[-2:], result.flows, atol=1e-14)

    def test_reversed_interface_component_preserves_external_flow(self):
        with tempfile.TemporaryDirectory() as folder:
            for file in RESISTANCE.glob('*.xml'):
                shutil.copyfile(file, Path(folder) / file.name)
            file = Path(folder) / 'netlist_surfaces.xml'
            tree = ET.parse(file)
            component = tree.find('./circuit/components/component')
            component.find('startNodeIndex').text = '2'
            component.find('endNodeIndex').text = '1'
            tree.write(file)
            adapter = self.make_adapter(directory=Path(folder))
            port = adapter.probe_port_response(0, .001, .001, [1., 2.], [29., 35.])
            np.testing.assert_allclose(port.pressure_response, [[10., 8.], [8., 12.]], atol=1e-14)
            adapter.update_state_all_and_finalize(0, .001, .001, [(0, 29., 1.), (4, 35., 2.)])
            self.assertAlmostEqual(adapter._history['surface:1'][-1][1][0], -1.)


class FullStarfishChecks(unittest.TestCase):
    def tearDown(self):
        get_default_netlist_manager().close()

    def test_repeat_output_is_rejected_before_existing_files_change(self):
        import solver
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            output, _, _ = solver.run_case(str(PASSIVE / 'input.xml'), folder,
                                           'solution', '001', 'output preservation')
            files = [p for p in Path(output).parent.rglob('*') if p.is_file()]
            before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
            with self.assertRaisesRegex(FileExistsError, 'already exist'):
                solver.run_case(str(PASSIVE / 'input.xml'), folder, 'solution', '001', 'repeat')
            self.assertEqual(before, {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files})

    def test_memory_rollover_output_phase_and_endpoint_matching(self):
        import solver
        import SolverLib.class1DflowSolver as flow_module
        original = flow_module.FlowSolver
        observations = []

        def construct(*args, **kwargs):
            instance = original(*args, **kwargs)
            observation = {'memory_size': instance.vascularNetwork.runtimeMemoryManager.memoryArraySizeTime,
                           'steps': instance.nTSteps, 'saved_counts': []}
            observations.append(observation)
            publication = instance.vascularNetwork

            def checked_publication():
                accepted = int(get_default_netlist_manager().adapter._state.accepted_steps)
                if accepted != instance.currentTimeStep[0] + 1:
                    raise AssertionError('circuit acceptance must precede network publication')
                observation['saved_counts'].append(accepted)
                publication()
            instance.numericalObjects = [checked_publication if item is publication else item
                                         for item in instance.numericalObjects]
            return instance

        with tempfile.TemporaryDirectory() as folder:
            case = Path(folder) / 'case'
            shutil.copytree(PASSIVE, case)
            arrays = []
            for index, memory in enumerate((.0002, 8.)):
                tree = ET.parse(case / 'input.xml')
                tree.find('./simulationContext/maxMemory').text = str(memory)
                tree.write(case / 'input.xml')
                with patch.object(flow_module, 'FlowSolver', construct), redirect_stdout(io.StringIO()):
                    output, _, _ = solver.run_case(str(case / 'input.xml'), str(Path(folder) / str(index)),
                                                   'solution', '001', 'closed-loop memory validation')
                with h5py.File(output) as file:
                    vessel = next(iter(file['vessels'].values()))
                    arrays.append({key: vessel[key][...] for key in ('Psol', 'Qsol', 'Asol')})
                directory = Path(output).parent
                p0 = np.loadtxt(directory / 'netlistPressures_surface_0.dat')
                q0 = np.loadtxt(directory / 'netlistFlows_surface_0.dat')
                q4 = np.loadtxt(directory / 'netlistFlows_surface_4.dat')
                count = observations[-1]['steps']
                self.assertEqual(len(p0), count + 1)
                np.testing.assert_array_equal(p0[:, 0], np.arange(count + 1))
                np.testing.assert_allclose(arrays[-1]['Psol'][:, 0], p0[:, 1], atol=1e-8, rtol=5e-11)
                np.testing.assert_allclose(-arrays[-1]['Qsol'][:, 0], q0[:, 1], atol=1e-12, rtol=5e-11)
                np.testing.assert_allclose(arrays[-1]['Qsol'][:, -1], q4[:, 1], atol=1e-12, rtol=5e-11)
            self.assertLess(observations[0]['memory_size'], observations[0]['steps'])
            for observation in observations:
                self.assertEqual(observation['saved_counts'], list(range(1, observation['steps'] + 1)))
            for key in arrays[0]:
                np.testing.assert_array_equal(arrays[0][key], arrays[1][key])

    def test_unsupported_initialization_and_cycle_profiles_fail(self):
        from SolverLib.class1DflowSolver import FlowSolver
        from NetworkLib.classBoundaryConditions import Netlist
        instance = FlowSolver.__new__(FlowSolver)
        bc = Netlist()
        bc.networkDirectory = str(PASSIVE)
        instance.venousPool = None
        instance.vascularNetwork = SimpleNamespace(boundaryConditions={0: [bc]},
            initialsationMethod='Auto', solvingSchemeField='MacCormack_Flux')
        with self.assertRaisesRegex(NotImplementedError, 'ConstantPressure'):
            instance.validateClosedLoopProfile()
        instance.closedLoopBoundaryGroup = object()
        instance.cycleMode = True
        with self.assertRaisesRegex(NotImplementedError, 'cycleMode'):
            instance.MacCormack_Field()


@unittest.skipUnless(WORKER.is_file(), 'build the native closed-loop validation worker')
class NativeCppChecks(unittest.TestCase):
    def test_static_diode_modes_match_native_cpp(self):
        from UnitTesting.closed_loop_cpp_reference import CppClosedLoopAdapter
        with tempfile.TemporaryDirectory() as folder:
            for file in RESISTANCE.glob('*.xml'):
                shutil.copyfile(file, Path(folder) / file.name)
            file = Path(folder) / 'netlist_surfaces.xml'
            tree = ET.parse(file)
            tree.find('./circuit/components/component/type').text = 'diode'
            tree.write(file)
            adapters = [cls(file, delt=.001, surface_ids=[0, 4])
                        for cls in (CppClosedLoopAdapter, NetlistClosedLoopPyAdapter)]
            modes = []
            try:
                for n in range(16):
                    q = [1. if n % 4 < 2 else -1., 2.]
                    p = [29. if n % 4 < 2 else -20., 3.]
                    results = []
                    for adapter in adapters:
                        response_ = adapter.probe_port_response(n, (n+1)*.001, .001, q, p)
                        u = np.where(response_.flow_input_mask, q, p)
                        accepted_p = response_.pressure_offset + response_.pressure_response @ u
                        accepted_q = response_.flow_offset + response_.flow_response @ u
                        adapter.update_state_all_and_finalize(n, (n+1)*.001, .001,
                            list(zip([0, 4], accepted_p, accepted_q)))
                        results.append((response_.flow_input_mask.copy(), accepted_p, accepted_q))
                    for old, new in zip(*results):
                        np.testing.assert_allclose(old, new, atol=1e-12, rtol=5e-11)
                    modes.append(bool(results[0][0][0]))
                self.assertEqual(set(modes), {False, True})
            finally:
                for adapter in adapters:
                    adapter.close()

    def test_native_adapter_does_not_call_numpy_circuit_kernel(self):
        from UnitTesting.closed_loop_cpp_reference import CppClosedLoopAdapter
        adapter = CppClosedLoopAdapter(RESISTANCE / 'netlist_surfaces.xml', delt=.001, surface_ids=[0, 4])
        try:
            adapter.load()
            with patch.object(adapter._kernel, 'solve_closed_loop_diode_timestep',
                              side_effect=AssertionError('NumPy numerical kernel was called by C++ backend')):
                response_ = adapter.probe_port_response(0, .001, .001, [1., 2.], [29., 35.])
                np.testing.assert_allclose(response_.pressure_response, [[10., 8.], [8., 12.]], atol=1e-14)
                adapter.update_state_all_and_finalize(0, .001, .001, [(0, 29., 1.), (4, 35., 2.)])
        finally:
            adapter.close()

    def test_native_response_and_carried_rc_history(self):
        from UnitTesting.closed_loop_cpp_reference import CppClosedLoopAdapter
        for directory in (RESISTANCE, PASSIVE, ROOT / 'ext/tests/closed_loop_controlled'):
            adapters = [cls(directory / 'netlist_surfaces.xml', delt=.001, surface_ids=[0, 4])
                        for cls in (CppClosedLoopAdapter, NetlistClosedLoopPyAdapter)]
            try:
                for n in range(32):
                    # Explicit synthetic prescribed-flow sequence; SI for PASSIVE,
                    # arbitrary consistent units for the analytical resistor case.
                    scale = 1. if directory == RESISTANCE else 1e-5
                    q = scale * np.asarray([(n % 5) - 2., 1. - n % 3])
                    trials = []
                    for adapter in adapters:
                        response_ = adapter.probe_port_response(n, (n+1)*.001, .001, q, [0., 0.])
                        p = response_.pressure_offset + response_.pressure_response @ q
                        trial = adapter.solve_trial(n, (n+1)*.001, .001, q, p)
                        adapter.stage_trial(trial)
                        adapter.update_state_all_and_finalize(n, (n+1)*.001, .001,
                            list(zip([0, 4], p, q)))
                        trials.append(trial)
                    # Native snapshots expose physical current getters, not
                    # the old-history columns of the reference solve vector.
                    for owner in adapters[0]._observations:
                        for axis, atol in ((0, 1e-8), (1, 1e-12), (2, 1e-12)):
                            np.testing.assert_allclose(adapters[0]._physical_values(owner, trials[0].published)[axis],
                                adapters[1]._physical_values(owner, trials[1].published)[axis], rtol=5e-11, atol=atol)
                for owner in adapters[0]._history:
                    for axis, atol in ((0, 1e-8), (1, 1e-12), (2, 1e-12)):
                        np.testing.assert_allclose(np.stack([x[axis] for x in adapters[0]._history[owner]]),
                            np.stack([x[axis] for x in adapters[1]._history[owner]]), rtol=5e-11, atol=atol)
            finally:
                for adapter in adapters:
                    adapter.close()


if __name__ == '__main__':
    unittest.main()
