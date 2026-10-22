#!/usr/bin/env python3
"""Create a separate SI 1D closed-loop case from the existing blood-loss tree."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from UtilityLib.netlistPyAdapter import netlist_source_directory


def build(destination, duration=60.):
    if destination.exists():
        raise FileExistsError('new case directory must not exist: '+str(destination))
    tutorial = ROOT/'examples/cr_sf_tutorial_demo/heart_model'
    native = netlist_source_directory().parent/'tests/05-HeartModel-ClosedLoop/2.SimFiles-Benchmark'
    sources = [tutorial/name for name in ('input.xml', 'netlist_surfaces.xml', 'bloodLossObserver.py',
        'bloodLossObserver_reference.py', 'elastanceController_reference.py')]
    sources += [native/'netlist_closed_loop_downstream.xml', native/'solver.inp',
                ROOT/'ext/tests/closed_loop_heart/elastanceController.py']
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    tree = ET.parse(tutorial/'input.xml')
    tree.find('./simulationContext/totalTime').text = str(duration)
    tree.find('./simulationContext/description').text = '1D valved heart, systemic beds, venous return and independent hemorrhage drain; SI'
    tree.find('./simulationContext/maxMemory').text = '128.0'
    tree.find('./initialisationControls/initialsationMethod').text = 'ConstantPressure'
    boundary = ET.parse(tutorial/'netlist_surfaces.xml')
    heart_return = boundary.find("./circuit[circuitIndex='1']/nodes/node[index='6']")
    heart_return.remove(heart_return.find('prescribedPressureType'))
    for index in ('2', '3'):
        tail = boundary.find("./circuit[circuitIndex='{}']/nodes/node[index='4']".format(index))
        tail.remove(tail.find('prescribedPressureType'))
    downstream = ET.parse(native/'netlist_closed_loop_downstream.xml')
    for component in downstream.findall('./circuit/components/component'):
        value = component.find('parameterValue')
        # Native source: Pa, mm^3, seconds. Starfish: Pa, m^3, seconds.
        factor = 1e-9 if component.findtext('type') == 'capacitor' else 1e9
        value.text = str(float(value.text)*factor)
    for node in downstream.findall('./circuit/nodes/node'):
        old = node.find('upstreamConnectivity')
        if old is not None:
            node.remove(old)
        node.find('initialPressure').text = '0' if node.findtext('index') == '4' else '533.2'
        links = {'1': ((1, 4), (2, 4)), '3': ((0, 6),)}.get(node.findtext('index'), ())
        if links:
            connectivity = ET.SubElement(node, 'upstreamConnectivity')
            for surface, local in links:
                connection = ET.SubElement(connectivity, 'connection')
                ET.SubElement(connection, 'upstreamCircuitSurfaceIndex').text = str(surface)
                ET.SubElement(connection, 'connectsToUpstreamNode').text = str(local)
    destination.mkdir(parents=True)
    tree.write(destination/'input.xml', encoding='utf-8', xml_declaration=True)
    boundary.write(destination/'netlist_surfaces.xml', encoding='utf-8', xml_declaration=True)
    downstream.write(destination/'netlist_closed_loop_downstream.xml', encoding='utf-8', xml_declaration=True)
    for name in ('bloodLossObserver.py','bloodLossObserver_reference.py','elastanceController_reference.py'):
        shutil.copyfile(tutorial/name, destination/name)
    shutil.copyfile(ROOT/'ext/tests/closed_loop_heart/elastanceController.py', destination/'elastanceController.py')
    (destination/'source_manifest.json').write_text(json.dumps({'source_sha256': hashes,
        'duration_s': duration, 'units': 'Pa, m^3/s, m^3, seconds',
        'physical_surface_map': {'0':'heart / proximal vessel 1', '1':'RCR / distal vessel 2',
                                '2':'RCR / distal vessel 4', '3':'external hemorrhage / distal vessel 5'},
        'return_surface_ids':[0,1,2], 'independent_loss_surface_ids':[3],
        'return_parameters': {'R1_pa_s_m3':1.5e7, 'R2_pa_s_m3':1e6, 'C_m3_pa':2e-7},
        'changes': ['preserve original 1D vessels, CFL, fluid, SI heart and feedback law',
                    'replace fixed heart filling and systemic tail reservoirs with shared return',
                    'use source 0D venous R/R/C topology, convert mm^3 units to m^3',
                    'initialize return at original fixed filling pressure 533.2 Pa',
                    'ConstantPressure initialization; 128 MB runtime buffer',
                    'new native controller uses linear CSV diagnostics; scalar law unchanged']}, indent=2)+'\n')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=ROOT/'examples/closed_loop_blood_loss_heart')
    parser.add_argument('--duration', type=float, default=60.)
    args = parser.parse_args()
    print(build(args.destination.resolve(), args.duration))
