#!/usr/bin/env python3
"""Run the new 1D hemorrhage circulation with actual backend controller traces."""

import argparse
import csv
import json
from pathlib import Path
import shutil
import sys
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from UnitTesting.run_example_netlist_comparisons import (
    run_backend, worker_run, snapshot, compare_outputs, save_json, case_markdown, classify)

TRACE_COLUMNS = ('step','time_s','phase_s','period_s','heart_rate_bpm','controller_lost_volume_m3',
                 'delta_heart_rate_bpm','debt_bpm','elastance_pa_per_m3')


def trace_adapter(base, backend):
    class Tracked(base):
        def load(self, dt=None):
            result = super().load(dt)
            if backend == 'python' and not hasattr(self, '_heart_trace'):
                self.output_directory.mkdir(parents=True, exist_ok=True)
                self._heart_trace = (self.output_directory/'heart_controller_trace.csv').open('x', buffering=1)
                self._heart_writer = csv.writer(self._heart_trace)
                self._heart_writer.writerow(TRACE_COLUMNS)
                self._write_heart_state()
            return result

        def _write_heart_state(self):
            matches = [(spec,runtime) for spec,runtime in zip(self._schedule.python_controllers,
                        self._controlled_state.controllers.python_runtime)
                       if spec.target_binding.circuit_owner == 'surface:1'
                       and spec.target_binding.target_kind == 'component_parameter'
                       and spec.target_binding.target.component_index == 3]
            if len(matches) != 1:
                raise ValueError('expected one actual LV feedback controller on physical surface 0 / component 3')
            _, runtime = matches[0]
            state = runtime.state
            target = self._controlled_state.targets['surface:1'].component_parameter_values[2]
            self._heart_writer.writerow((int(self._state.accepted_steps), float(self._controlled_state.time),
                state.periodic_time, state.heart_period, state.heart_rate, state.total_blood_loss,
                state.delta_heart_rate, state.debt_delta, float(target)))

        def finalize_timestep(self, timestep):
            before = self._last_finalized
            result = super().finalize_timestep(timestep)
            if backend == 'python' and self._last_finalized != before:
                self._write_heart_state()
            return result

        def close(self):
            if backend == 'cpp' and getattr(self,'_native',None) is not None:
                self._native.close()
                self._native = None
                source = self._normalized_directory/'heart_controller_trace.csv'
                if source.exists() and self.output_directory is not None:
                    self.output_directory.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, self.output_directory/source.name)
            if backend == 'python' and getattr(self,'_heart_trace',None) is not None:
                self._heart_trace.close()
            return super().close()
    Tracked.__name__ = 'HeartTraceCppAdapter' if backend == 'cpp' else 'HeartTraceNumpyAdapter'
    return Tracked


def child(source, backend, target, diagnostics):
    if backend == 'cpp':
        import UnitTesting.closed_loop_cpp_reference as module
        name = 'CppClosedLoopAdapter'
    else:
        import UtilityLib.netlistClosedLoopPyAdapter as module
        name = 'NetlistClosedLoopPyAdapter'
    tracked = trace_adapter(getattr(module,name),backend)
    with patch.object(module,name,tracked):
        return worker_run(source,backend,target,diagnostics=diagnostics)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',type=Path,default=ROOT/'examples/closed_loop_blood_loss_heart/input.xml')
    parser.add_argument('--duration',type=float,help='override only the private input copy, for a pilot')
    parser.add_argument('--run-case',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--backend',choices=('cpp','python'),help=argparse.SUPPRESS)
    parser.add_argument('--target',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--diagnostics',action='store_true',help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.run_case:
        raise SystemExit(child(args.run_case,args.backend,args.target,args.diagnostics))
    source = args.case.resolve()
    output = source.parent/'results_closed_loop'
    output.mkdir(exist_ok=True)
    index=1
    while (output/f'run_{index:03d}').exists():
        index+=1
    run=output/f'run_{index:03d}'
    run.mkdir()
    copied,hashes=snapshot(source,run/'inputs')
    manifest=source.parent/'source_manifest.json'
    if manifest.exists():
        shutil.copyfile(manifest,run/manifest.name)
    if args.duration is not None:
        tree=ET.parse(copied)
        tree.find('./simulationContext/totalTime').text=str(args.duration)
        tree.write(copied,encoding='utf-8',xml_declaration=True)
    row=dict(case=source.parent.name,source=str(source),run_directory=str(run),source_sha256=hashes,
             **classify(copied))
    print('RESULTS '+str(run),flush=True)
    for backend in ('cpp','python'):
        print('START '+backend,flush=True)
        row[backend]=run_backend(copied,backend,run,diagnostics=True,worker_script=Path(__file__).resolve())
        save_json(run/'comparison.json',row)
        if row[backend]['status']!='completed':
            row.update(status='failed_'+backend,reason=row[backend].get('error','see console log'))
            save_json(run/'comparison.json',row)
            (run/'comparison.md').write_text(case_markdown(row))
            raise SystemExit(row['reason'])
        print('DONE '+backend+' solve {:.3f} s'.format(row[backend]['solve_seconds']),flush=True)
    row['accuracy']=compare_outputs(row['cpp'],row['python'])
    row['status']='passed' if row['accuracy']['passed'] else 'failed_accuracy'
    save_json(run/'comparison.json',row)
    (run/'comparison.md').write_text(case_markdown(row))
    # Scientific monitors and plots are deliberately outside the solve timers.
    from UnitTesting.analyze_closed_loop_heart import analyze
    monitors=analyze(row,run)
    row['monitor_validation']=monitors
    if not monitors['passed']:
        row['status']='failed_monitor_validation'
    save_json(run/'comparison.json',row)
    (run/'comparison.md').write_text(case_markdown(row))
    print('REPORT '+str(run/'heart_report.md'),flush=True)
    raise SystemExit(0 if row['status']=='passed' and monitors['passed'] else 1)


if __name__=='__main__':
    main()
