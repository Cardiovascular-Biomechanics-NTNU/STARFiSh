"""Mixed return/drain topology and independent native/reference histories."""

import copy
from pathlib import Path
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET

import numpy as np

from UnitTesting.build_closed_loop_heart import build
from UtilityLib.netlistClosedLoopPyAdapter import NetlistClosedLoopPyAdapter

ROOT=Path(__file__).resolve().parents[1]


class ClosedHeartChecks(unittest.TestCase):
    def test_builder_preserves_1d_tree_and_keeps_bleed_outside_return(self):
        with tempfile.TemporaryDirectory() as folder:
            case=build(Path(folder)/'heart')
            old=ET.parse(ROOT/'examples/cr_sf_tutorial_demo/heart_model/input.xml')
            new=ET.parse(case/'input.xml')
            self.assertEqual(ET.tostring(old.find('./vessels')),ET.tostring(new.find('./vessels')))
            self.assertEqual(old.findtext('./simulationContext/CFL'),new.findtext('./simulationContext/CFL'))
            self.assertEqual(new.findtext('./simulationContext/totalTime'),'60.0')
            return_tree=ET.parse(case/'netlist_closed_loop_downstream.xml')
            connected={int(x.text) for x in return_tree.findall('.//upstreamCircuitSurfaceIndex')}
            self.assertEqual(connected,{0,1,2})
            boundary=ET.parse(case/'netlist_surfaces.xml')
            self.assertEqual(boundary.findtext("./circuit[circuitIndex='4']/nodes/node[index='2']/prescribedPressureType"),'fixed')
            self.assertIsNone(boundary.find("./circuit[circuitIndex='1']/nodes/node[index='6']/prescribedPressureType"))
            for index in ('2','3'):
                self.assertIsNone(boundary.find(f"./circuit[circuitIndex='{index}']/nodes/node[index='4']/prescribedPressureType"))

    def test_mixed_independent_drain_response_and_histories(self):
        with tempfile.TemporaryDirectory() as folder:
            case=Path(folder)
            for source in (ROOT/'ext/tests/closed_loop_resistance').glob('*.xml'):
                shutil.copyfile(source,case/source.name)
            file=case/'netlist_surfaces.xml'
            tree=ET.parse(file)
            circuit=copy.deepcopy(tree.find('./circuit'))
            circuit.find('circuitIndex').text='3'
            circuit.find('./components/component/parameterValue').text='10'
            node=circuit.find("./nodes/node[index='2']")
            ET.SubElement(node,'prescribedPressureType').text='fixed'
            node.find('initialPressure').text='0'
            tree.getroot().append(circuit)
            tree.write(file)
            classes=[NetlistClosedLoopPyAdapter]
            if (ROOT/'ext/build/crimson_closed_loop_validation_worker').is_file():
                from UnitTesting.closed_loop_cpp_reference import CppClosedLoopAdapter
                classes.append(CppClosedLoopAdapter)
            adapters=[cls(file,delt=.001,surface_ids=[0,4,8]) for cls in classes]
            try:
                for n in range(16):
                    q=np.array([1.+.1*np.sin(n),2.,.5+.1*np.cos(n)])
                    results=[]
                    for adapter in adapters:
                        port=adapter.probe_port_response(n,(n+1)*.001,.001,q,[3.,3.,0.])
                        self.assertEqual(adapter.connected_surface_ids,[0,4])
                        self.assertEqual(adapter.independent_surface_ids,[8])
                        np.testing.assert_allclose(port.pressure_response,[[10,8,0],[8,12,0],[0,0,10]],atol=1e-12)
                        np.testing.assert_allclose(port.pressure_offset,[3,3,0],atol=1e-12)
                        p=port.pressure_offset+port.pressure_response@q
                        trial=adapter.solve_trial(n,(n+1)*.001,.001,q,p)
                        adapter.stage_trial(trial)
                        adapter.update_state_all_and_finalize(n,(n+1)*.001,.001,list(zip([0,4,8],p,q)))
                        results.append(trial.published)
                    for expected in results[1:]:
                        np.testing.assert_allclose(results[0],expected,rtol=5e-11,atol=1e-12)
            finally:
                for adapter in adapters:
                    adapter.close()


if __name__=='__main__':
    unittest.main()
