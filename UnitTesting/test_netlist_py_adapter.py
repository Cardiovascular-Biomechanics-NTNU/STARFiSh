"""Coupling invariants using real NumPy circuits; no C++ runtime required."""

import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from NetworkLib.netlistManager import NetlistBoundaryManager
from UtilityLib.netlistPyAdapter import NetlistPyAdapter


class NetlistPyAdapterChecks(unittest.TestCase):
    def make_adapter(self, output=None, controlled=False):
        kind = "controllers" if controlled else "passive"
        return NetlistPyAdapter(ROOT / "ext/tests" / kind / "netlist_surfaces.xml",
                                delt=0.001, surface_ids=[0], output_directory=output)

    def test_probes_do_not_accept_and_close_omits_incomplete_step(self):
        with tempfile.TemporaryDirectory() as output:
            adapter = self.make_adapter(output)
            adapter.load()
            self.assertEqual(adapter.surface_to_circuit, {0: 1})
            for flow in (1e-5, -1e-5, 2e-5):
                self.assertEqual(adapter.compute_interface_data(0, 0, .001, .001, flow),
                                 (True, False, 100.0, 0.0))
            self.assertEqual(len(adapter._history[0]), 1)
            adapter.update_state_all_and_finalize(0, .001, .001, [(0, .001, 1e-5)])
            adapter.finalize_timestep(0)
            adapter.start_timestep(1, .002, .001)
            adapter.update_state(0, 1, .002, .001, .002, 2e-5)
            adapter.close()
            adapter.close()
            rows = np.loadtxt(Path(output) / "netlistPressures_surface_0.dat", ndmin=2)
            self.assertEqual(rows.shape, (2, 3))
            np.testing.assert_allclose(rows[:, 0], [0, 1])
            np.testing.assert_allclose(rows[1, 1:], [.001, 0.0])

    def test_controller_keeps_old_worker_post_finalize_timing(self):
        adapter = self.make_adapter(controlled=True)
        try:
            slopes = []
            for n in range(3):
                data = adapter.compute_interface_data(0, n, (n+1)*.001, .001, 1e-5)
                slopes.append(data[2])
                adapter.update_state_all_and_finalize(n, (n+1)*.001, .001,
                    [(0, data[2]*1e-5+data[3], 1e-5)])
            self.assertEqual(slopes, [100., 200., 400.])
        finally:
            adapter.close()

    def test_bad_lifecycle_and_changed_dt_fail_before_acceptance(self):
        adapter = self.make_adapter()
        try:
            adapter.load()
            with self.assertRaises(ValueError):
                adapter.load(.002)
            with self.assertRaises(RuntimeError):
                adapter.start_timestep(1, .002, .001)
            adapter.start_timestep(0, .001, .001)
            with self.assertRaises(RuntimeError):
                adapter.finalize_timestep(0)
            with self.assertRaises(ValueError):
                adapter.update_state_all_and_finalize(0, .001, .001, [])
            with self.assertRaises(ValueError):
                adapter.update_state_all_and_finalize(0, .001, .001, [(0, np.nan, 0)])
            with self.assertRaises(RuntimeError):
                adapter.register_surfaces([0, 7])
            self.assertEqual(len(adapter._history[0]), 1)
        finally:
            adapter.close()

    def test_builtin_elastance_initializes_before_first_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            tree = ET.parse(ROOT / "ext/tests/passive/netlist_surfaces.xml")
            component = tree.getroot().find("./circuit/components/component")
            component.find("type").text = "volumeTrackingPressureChamber"
            component.find("parameterValue").text = "5.0"
            ET.SubElement(component, "initialVolume").text = "2.0"
            control = ET.SubElement(component, "control")
            ET.SubElement(control, "type").text = "leftVentricularElastance"
            path = Path(directory) / "netlist_surfaces.xml"
            tree.write(path)
            adapter = NetlistPyAdapter(path, delt=.001, surface_ids=[0])
            try:
                data = adapter.compute_interface_data(0, 0, .001, .001, 1e-5)
                self.assertAlmostEqual(data[2], .001 * 4.10246e-3, places=15)
                self.assertAlmostEqual(data[3], 2.0 * 4.10246e-3, places=15)
                self.assertEqual(int(adapter._controller_state.current_timestep_index), 0)
            finally:
                adapter.close()

    def test_global_manager_uses_numpy_and_resets_between_cases(self):
        manager = NetlistBoundaryManager()
        for _ in range(2):
            try:
                manager.register_boundary(0, vessel_id=3, position=-1,
                    netlist_file=str(ROOT / "ext/tests/passive/netlist_surfaces.xml"))
                self.assertEqual(manager.compute_interface_data(0, 0, .001, .001, 1000., 1e-5),
                                 (True, False, 100., 0.))
                self.assertIsInstance(manager.adapter, NetlistPyAdapter)
                manager.record_boundary_state(0, 0, .001, .001, .001, 1e-5)
                manager.finalize_timestep(0)
            finally:
                manager.close()
            self.assertEqual(manager.boundaries, {})
            self.assertIsNone(manager.adapter)

    def test_surface_registration_rejects_conflicting_endpoints(self):
        manager = NetlistBoundaryManager()
        manager.register_boundary(0, vessel_id=3, position=-1)
        manager.register_boundary(0, vessel_id=3, position=-1)
        with self.assertRaisesRegex(ValueError, "conflicting"):
            manager.register_boundary(0, vessel_id=4, position=-1)
        with self.assertRaisesRegex(ValueError, "conflicting"):
            manager.register_boundary(0, vessel_id=3, position=0)
        manager.close()

    def test_top_level_location_is_used_and_numpy_path_does_not_import_jax(self):
        import netlist_config
        adapter = self.make_adapter()
        with patch.object(netlist_config, "NETLIST_PY_DIRECTORY", "/missing/netlist_py"):
            with self.assertRaisesRegex(FileNotFoundError, "netlist_config.py"):
                adapter.load()
        adapter.close()
        code = ("import sys; from UtilityLib.netlistPyAdapter import NetlistPyAdapter; "
                "a=NetlistPyAdapter('ext/tests/passive/netlist_surfaces.xml', "
                "delt=.001, surface_ids=[0]); a.load(); "
                "assert 'jax' not in sys.modules; "
                "assert 'UtilityLib.crimsonNetlistAdapter' not in sys.modules; a.close()")
        subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()
