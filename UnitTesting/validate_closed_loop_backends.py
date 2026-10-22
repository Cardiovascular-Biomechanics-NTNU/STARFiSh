#!/usr/bin/env python3
"""Run the passive SI closed-circulation fixture with C++ and NumPy.

Both backends supply their own circuit responses/history to the same Starfish
simultaneous characteristic solve. Additional NumPy grid refinements measure
the vessel/compliance volume ledger. This diagnostic is specific to the
single-vessel R/RC fixture, not a generic volume interpretation of any netlist.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from UnitTesting.run_example_netlist_comparisons import run_backend, save_json
from UtilityLib.netlistPyAdapter import netlist_source_directory


def conservation(run, source):
    root = ET.parse(source).getroot()
    vessels = root.findall('./vessels/vessel')
    if (len(vessels) != 1 or vessels[0].findtext('./geometry/geometryType') != 'uniform'
            or vessels[0].find('./geometry/length').get('unit') != 'm'):
        raise ValueError('volume ledger is defined only for the passive uniform single-vessel fixture')
    length = float(vessels[0].findtext('./geometry/length'))
    ret = ET.parse(source.parent / 'netlist_closed_loop_downstream.xml')
    components = ret.findall('./circuit/components/component')
    if [(c.findtext('type'), c.findtext('startNodeIndex'), c.findtext('endNodeIndex'))
            for c in components] != [('resistor', '1', '2'), ('capacitor', '1', '3')]:
        raise ValueError('the fixture ledger requires the declared R/RC return topology')
    capacitance = float(components[1].findtext('parameterValue'))
    output = Path(run['hdf5']).parent
    down_p = np.loadtxt(output / 'netlistPressures_downstreamCircuit_0.dat')[:, 1:]
    down_q = np.loadtxt(output / 'netlistFlows_downstreamCircuit_0.dat')[:, 1:]
    port_p = [np.loadtxt(output / ('netlistPressures_surface_{}.dat'.format(i)))[:, 1:] for i in (0, 4)]
    port_q = [np.loadtxt(output / ('netlistFlows_surface_{}.dat'.format(i)))[:, 1:] for i in (0, 4)]
    dt = run['coupling']['dt_s']
    with h5py.File(run['hdf5']) as file:
        vessel = next(iter(file['vessels'].values()))
        area = vessel['Asol'][...]
        # The uniform fixture uses endpoint-inclusive z, not the legacy HDF
        # dz attribute (which currently stores length/N).
        volume = np.trapezoid(area, dx=length/(area.shape[1]-1), axis=1)
        pressure, flow = vessel['Psol'][...], vessel['Qsol'][...]
    total = volume + capacitance * (down_p[:, 0] - down_p[:, 2])
    max_abs = lambda values: float(np.max(np.abs(values), initial=0.))
    result = {
        'dt_s': dt, 'vessel_nodes': int(area.shape[1]),
        'accepted_steps': run['coupling']['accepted_steps'],
        'runtime_memory_samples': run['coupling']['runtime_memory_samples'],
        'runtime_memory_chunks': run['coupling']['runtime_memory_chunks'],
        'max_shared_kcl_residual_m3_s': max(max_abs(port_q[0][:, 0]-down_q[:, 0]-down_q[:, 1]),
                                            max_abs(port_q[1][:, 0]+down_q[:, 0])),
        'max_shared_pressure_residual_pa': max(max_abs(port_p[0][:, 1]-down_p[:, 0]),
                                               max_abs(port_p[1][:, 1]-down_p[:, 1])),
        'max_capacitor_history_residual_m3_s': max_abs(
            down_q[1:, 1] - capacitance*np.diff(down_p[:, 0]-down_p[:, 2])/dt),
        'max_endpoint_pressure_residual_pa': max(max_abs(pressure[:, 0]-port_p[0][:, 0]),
                                                 max_abs(pressure[:, -1]-port_p[1][:, 0])),
        'max_endpoint_flow_residual_m3_s': max(max_abs(-flow[:, 0]-port_q[0][:, 0]),
                                               max_abs(flow[:, -1]-port_q[1][:, 0])),
        'initial_total_volume_m3': float(total[0]),
        'final_total_volume_m3': float(total[-1]),
        'max_total_volume_defect_m3': max_abs(total-total[0]),
        'max_relative_total_volume_defect': max_abs(total-total[0])/abs(float(total[0])),
        'interpretation': 'V_total = trapezoid(A,z) + C*(p_return_1-p_reference_3); no physical external source or loss. Total-volume defect includes the existing 1D discretization error.',
    }
    result['algebraic_checks_passed'] = (
        max(result['max_shared_kcl_residual_m3_s'], result['max_capacitor_history_residual_m3_s'],
            result['max_endpoint_flow_residual_m3_s']) <= 1e-12
        and max(result['max_shared_pressure_residual_pa'], result['max_endpoint_pressure_residual_pa']) <= 1e-8)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, default=ROOT / 'examples/closed_loop_passive')
    parser.add_argument('--no-refinement', action='store_true')
    args = parser.parse_args()
    case = args.case.resolve()
    if not (case / 'input.xml').is_file():
        raise SystemExit('Copy ext/tests/closed_loop_passive/ into examples/closed_loop_passive/ first.')
    subprocess.run([sys.executable, '-B', str(ROOT / 'UnitTesting/run_example_netlist_comparisons.py'),
                    '--examples', str(case)], cwd=ROOT, check=True)
    aggregate = json.loads((case / 'netlist_cpp_python_comparison.json').read_text())
    if len(aggregate['cases']) != 1 or aggregate['cases'][0]['status'] != 'passed':
        raise SystemExit('A successful native C++ and NumPy comparison is required; inspect the saved case report.')
    row = aggregate['cases'][0]
    directory = Path(row['run_directory'])
    result = {'comparison_report': str(directory / 'comparison.md'),
              'conservation': {backend: conservation(row[backend], case / 'input.xml')
                               for backend in ('cpp', 'python')}, 'refinements': []}
    if not args.no_refinement:
        for nodes in (80, 160):
            destination = directory / 'refinement' / ('N_{:03d}'.format(nodes))
            inputs = destination / 'source'
            inputs.mkdir(parents=True)
            for name in ('input.xml', 'netlist_surfaces.xml', 'netlist_closed_loop_downstream.xml'):
                shutil.copyfile(case / name, inputs / name)
            tree = ET.parse(inputs / 'input.xml')
            tree.find('./vessels/vessel/geometry/N').text = str(nodes)
            tree.write(inputs / 'input.xml', encoding='utf-8', xml_declaration=True)
            run = run_backend(inputs / 'input.xml', 'python', destination)
            if run['status'] != 'completed':
                raise RuntimeError('refinement failed: ' + run.get('error', 'see console.log'))
            diagnostic = conservation(run, inputs / 'input.xml')
            diagnostic['run'] = run
            result['refinements'].append(diagnostic)
    worker = ROOT / 'ext/build/crimson_closed_loop_validation_worker'
    result['provenance'] = {'cpp_worker_sha256': hashlib.sha256(worker.read_bytes()).hexdigest(),
        'netlist_py_source': str(netlist_source_directory()), 'numpy': np.__version__, 'python': sys.version,
        'cpp_probe_profile': 'native zero-flow initialization probe; each frozen QUERY solves twice with explicit cache invalidation to consume a latent first-flow guard after valve opening; no query publishes or accepts history; native full updates and finalization'}
    checks = [*result['conservation'].values(), *result['refinements']]
    result['passed'] = all(item['algebraic_checks_passed'] for item in checks)
    defects = [result['conservation']['python']['max_total_volume_defect_m3'],
               *(item['max_total_volume_defect_m3'] for item in result['refinements'])]
    result['volume_defect_decreases_with_grid_refinement'] = (
        all(b < a for a, b in zip(defects, defects[1:])) if len(defects) > 1 else None)
    if len(defects) > 1:
        result['passed'] &= result['volume_defect_decreases_with_grid_refinement']
    report = directory / 'closed_loop_validation.json'
    save_json(report, result)
    save_json(case / 'closed_loop_validation.json', result)
    lines = ['# Passive closed-loop validation', '',
        'Status: **{}**.'.format('passed' if result['passed'] else 'failed'), '',
        'Both complete Starfish runs use the same simultaneous characteristic algorithm.',
        'The C++ backend runs native CRIMSON subsection equations and carries its own histories.',
        'The Python backend uses NumPy/reference. Neither run replays the other backend\'s ports.', '',
        '| Run | Nodes | Steps | Buffer samples | Memory chunks | Max shared KCL residual (m³/s) | Max volume defect (m³) |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    runs = [('C++', result['conservation']['cpp']), ('NumPy', result['conservation']['python'])]
    runs += [('NumPy refinement', item) for item in result['refinements']]
    for label, item in runs:
        lines.append('| {} | {} | {} | {} | {} | {:.4g} | {:.4g} |'.format(label,
            item['vessel_nodes'], item['accepted_steps'], item['runtime_memory_samples'], item['runtime_memory_chunks'],
            item['max_shared_kcl_residual_m3_s'], item['max_total_volume_defect_m3']))
    lines += ['', 'The volume ledger is vessel volume plus return compliance storage. The electrical',
        'reference is not a physical bleed. Its total-volume defect includes the existing 1D',
        'discretization error; it is reported separately from algebraic junction conservation.', '',
        '[Accuracy and timing comparison](comparison.md). Full residuals, provenance and per-run metadata',
        'are in `closed_loop_validation.json`. Grid refinement retains the case CFL, so space and',
        'time are refined together; this does not independently establish either convergence order.', '']
    (directory / 'closed_loop_validation.md').write_text('\n'.join(lines))
    (case / 'closed_loop_validation.md').write_text('\n'.join(lines).replace('(comparison.md)',
        '(' + str(directory.relative_to(case)) + '/comparison.md)'))
    with (directory / 'comparison.md').open('a') as handle:
        handle.write('\n## Conservation and refinement\n\nSee [closed-loop validation](closed_loop_validation.md).\n')
    print('Closed-loop validation: ' + str(report), flush=True)
    print('Volume defects: ' + repr(defects), flush=True)
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
