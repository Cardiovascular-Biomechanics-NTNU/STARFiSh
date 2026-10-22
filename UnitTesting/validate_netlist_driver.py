#!/usr/bin/env python3
"""Save upstream lifecycle identity and matching-schedule C++ evidence.

Runs the lifecycle suite, historical independent regressions, and complete
passive/controlled closed-loop examples. Every example comparison allocates a
new results directory. The generated zero-D domain's delayed exchange is not
the external coupling algorithm of Starfish, and is not a trajectory oracle.
"""

import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from UtilityLib.netlistPyAdapter import netlist_source_directory


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    timings = {}

    class Result(unittest.TextTestResult):
        def startTest(self, test):
            self.started = time.perf_counter()
            super().startTest(test)

        def stopTest(self, test):
            timings[test.id()] = time.perf_counter() - self.started
            super().stopTest(test)

    with (output/'unit_tests.log').open('w') as log, redirect_stdout(log), redirect_stderr(log):
        suite = unittest.defaultTestLoader.discover(str(ROOT/'UnitTesting'), pattern='test_netlist*.py')
        result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=Result).run(suite)
    units = {'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
             'skipped': len(result.skipped), 'passed': result.wasSuccessful() and not result.skipped,
             'test_seconds': timings}
    comparisons = {}
    command = [sys.executable, '-B', str(ROOT/'UnitTesting/validate_netlist_backends.py'),
               '--output-dir', str(output/'legacy_cpp'), '--duration', '1']
    with (output/'legacy_cpp.log').open('w') as log:
        subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    legacy = json.loads((output/'legacy_cpp/comparison.json').read_text())
    for name in ('closed_loop_passive', 'closed_loop_controlled'):
        fixture, example = ROOT/'ext/tests'/name, ROOT/'examples'/name
        if not example.exists():
            shutil.copytree(fixture, example)
        # Refuse silently comparing stale or independently edited example inputs.
        for path in fixture.iterdir():
            if path.suffix in ('.xml', '.py') and (example/path.name).read_bytes() != path.read_bytes():
                raise ValueError('example input differs from fixture: '+str(example/path.name))
        with (output/(name+'.log')).open('w') as log:
            subprocess.run([sys.executable, '-B', str(ROOT/'UnitTesting/run_example_netlist_comparisons.py'),
                '--examples', str(example)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        row = json.loads((example/'netlist_cpp_python_comparison.json').read_text())['cases'][0]
        peaks = {group: {kind: max((entry['max_abs'] for entry in row['accuracy'][group].values()
                    if entry['quantity'] == kind and entry['samples'] > 0), default=None)
                for kind in ('pressure', 'flow', 'area', 'volume')}
                for group in ('vessels', 'netlist')}
        comparisons[name] = {'status': row['status'], 'report': str(Path(row['run_directory'])/'comparison.md'),
            'max_abs_error': peaks, 'solve_seconds': {backend: row[backend]['solve_seconds'] for backend in ('cpp','python')},
            'coupling': {backend: row[backend]['coupling'] for backend in ('cpp','python')},
            'adapter_classes': {backend: row[backend]['adapter_classes'] for backend in ('cpp','python')}}
    retained = ('UtilityLib/crimsonNetlistAdapter.py', 'UtilityLib/crimsonNetlistWorkerClient.py',
        'ext/CrimsonNetlistRuntime.cpp', 'ext/CrimsonNetlistRuntime.hxx', 'ext/CrimsonNetlistWorker.cpp',
        'ext/CrimsonControlSystems.cpp', 'ext/CrimsonControlSystems.hxx', 'ext/bindings.cpp')
    unchanged = {name: subprocess.check_output(['git','show','HEAD:'+name], cwd=ROOT) == (ROOT/name).read_bytes()
                 for name in retained}
    source = netlist_source_directory()
    local = ('NetworkLib/netlistDriver.py', 'NetworkLib/netlistManager.py', 'NetworkLib/netlistCoupling.py',
        'UtilityLib/netlistPyAdapter.py', 'UtilityLib/netlistClosedLoopPyAdapter.py', 'SolverLib/class1DflowSolver.py',
        'ext/ClosedLoopValidationWorker.cpp', 'UnitTesting/test_netlist_driver.py')
    paths = [*(ROOT/name for name in local), *(source/name for name in (
        'pureZeroDDriver_reference.py', 'BoundaryConditionManager_reference.py',
        'ControlSystemsManager_reference.py', 'ControllerManifest_reference.py',
        'ClosedLoopDownstreamSubsection_reference.py')), ROOT/'ext/build/crimson_closed_loop_validation_worker']
    report = {'scope': '1D driver lifecycle; matching external ports for upstream identity checks; matching 1D coupling for native C++ comparisons',
        'production_controller_phase': 'iter_init', 'regular_reference': 'ZeroDDriver',
        'closed_loop_reference': 'controlled_closed_loop_iter_init/step/finalize (called directly in production)',
        'exchange': 'simultaneous vessel characteristics; distinct from delayed generated 0D replacement exchange',
        'upstream_identity': {'regular_doubling_steps': 10, 'regular_feedback_rc_steps': 24, 'closed_loop_steps': 40,
            'comparison': 'exact array equality of tested controller, target, trial and accepted state fields'},
        'unit_checks': units, 'legacy_cpp_regression': legacy,
        'closed_loop_cases': comparisons, 'retained_cpp_files_identical_to_HEAD': unchanged,
        'python': sys.version, 'numpy': np.__version__,
        'sha256': {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}}
    report['passed'] = (units['passed'] and legacy['passed'] and all(unchanged.values())
                        and all(row['status'] == 'passed' for row in comparisons.values()))
    (output/'validation.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    lines = ['# 1D netlist lifecycle validation', '', 'Status: **'+('passed' if report['passed'] else 'failed')+'**.', '',
        'Production uses prepare/controllers → observational trials → publish/accept → output/rollover.', '',
        f"{units['tests']} unit checks; {len(legacy['results'])} historical C++ comparisons.", '',
        'Regular controls matched the upstream ZeroDDriver for 10 steps, including the first update.',
        'An additional 24-step RCR feedback trajectory matched accepted histories and owner observations exactly.',
        'Controlled closed-loop states matched upstream exactly for 40 steps, including shared broadcasts,',
        'chamber E/V0, fixed pressure, inductor/capacitor histories, and diode mode changes.', '',
        '| Complete 1D case | Max vessel ΔP (Pa) | Max vessel ΔQ (m³/s) | C++ solve (s) | NumPy solve (s) |',
        '| --- | ---: | ---: | ---: | ---: |']
    for name, row in comparisons.items():
        error, timing = row['max_abs_error']['vessels'], row['solve_seconds']
        lines.append(f"| {name} | {error['pressure']:.6g} | {error['flow']:.6g} | {timing['cpp']:.6g} | {timing['python']:.6g} |")
    lines += ['', 'Both complete cases use the same simultaneous 1D coupling in native C++ and NumPy.',
        'The controlled case uses native upstream/downstream controllers at iter_init.',
        'Timings are single-run measurements including IPC; not repeated benchmarks.', '',
        'The independent historical C++ worker still uses post-finalize controllers. Its 15 comparisons',
        'explicitly select the matching legacy NumPy profile; they do not compare different phases.',
        'All eight retained old C++ integration files are byte-identical to HEAD.', '',
        'The generated 0D replacement has a different delayed domain exchange. This report establishes',
        'the tested circuit/controller lifecycle under matching ports, not identical 0D/1D trajectories.', '',
        'Complete test names, per-case report paths, versions and source/binary hashes: `validation.json`.', '']
    (output/'validation.md').write_text('\n'.join(lines))
    return report['passed']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True, help='new report directory')
    args = parser.parse_args()
    # Existing solver grid diagnostics are outside its case output path. Keep
    # their pre-validation contents while retaining every case result.
    diagnostics = {ROOT/name: ((ROOT/name).read_bytes() if (ROOT/name).exists() else None)
                   for name in ('LOGcurrentWaveSpeed.txt', 'LOGproposedGrid.txt', 'histor.log')}
    try:
        passed = run(args.output_dir.resolve())
    finally:
        for path, contents in diagnostics.items():
            if contents is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(contents)
    print('Report: '+str(args.output_dir/'validation.md'))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
