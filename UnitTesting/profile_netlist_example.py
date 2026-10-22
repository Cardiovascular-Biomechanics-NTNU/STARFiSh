#!/usr/bin/env python3
"""Profile a complete Starfish example using retained C++ and in-process NumPy.

Fresh sequential processes isolate cases, not netlist calls. Each backend gets
an unprofiled timing run and a separate deterministic solve-loop profile. Independent
controllers use the explicit legacy phase for a matching-schedule comparison.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
import pstats
import shlex
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def export_profile(profiler, target):
    """Called by the isolated runner after profiling only FlowSolver.solve."""
    profiler.dump_stats(str(target/'solve.prof'))
    stats = pstats.Stats(profiler)
    entries = []
    for (filename, line, function), (primitive, calls, own, cumulative, _) in stats.stats.items():
        entries.append({'file': filename, 'line': line, 'function': function,
            'primitive_calls': primitive, 'calls': calls, 'self_seconds': own,
            'cumulative_seconds': cumulative})
    entries.sort(key=lambda row: row['cumulative_seconds'], reverse=True)
    summary = {'scope': 'FlowSolver.solve main thread; elapsed attribution including waits; excludes initialization/output shutdown and native child stacks',
        'total_calls': stats.total_calls, 'primitive_calls': stats.prim_calls,
        'total_attributed_seconds': stats.total_tt, 'functions': entries}
    (target/'solve_profile.json').write_text(json.dumps(summary, indent=2)+'\n')
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats('cumulative').print_stats(60)
    pstats.Stats(profiler, stream=stream).sort_stats('tottime').print_stats(60)
    (target/'solve_profile.txt').write_text(stream.getvalue())
    return {key: value for key, value in summary.items() if key != 'functions'}


def peak(metrics, group, quantity):
    return max((row['max_abs'] for row in metrics[group].values()
                if row['quantity'] == quantity and row['samples']), default=None)


def chart(run, baseline):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    labels, colors = ['C++ worker', 'NumPy in process'], ['#446a99', '#2a927c']
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.2), constrained_layout=True)
    for axis, key, title in ((axes[0], 'solve_seconds', 'Starfish solve wall time'),
                             (axes[1], 'netlist_seconds', 'All circuit adapter calls')):
        values = [baseline[b][key] for b in ('cpp','python')]
        axis.bar(labels, values, color=colors)
        axis.set_title(title)
        axis.set_ylabel('Seconds; unprofiled run')
        for i, value in enumerate(values):
            axis.text(i, value, f'{value:.3f}', ha='center', va='bottom')
        axis.set_ylim(0, max(values)*1.15)
    host = [baseline[b]['cpu_seconds']['starfish_process']['total'] for b in ('cpp','python')]
    child = [baseline[b]['cpu_seconds']['waited_children']['total'] for b in ('cpp','python')]
    axes[2].bar(labels, host, color='#6c8ba3', label='Starfish process')
    axes[2].bar(labels, child, bottom=host, color='#d5984c', label='Worker child')
    axes[2].set_title('CPU consumed during case run')
    axes[2].set_ylabel('CPU seconds; host plus waited children')
    axes[2].legend(frameon=False)
    fig.suptitle('Blood-loss heart example: native worker vs direct NumPy calls')
    fig.savefig(run/'timing.png', dpi=160)
    fig.savefig(run/'timing.svg')
    plt.close(fig)


def write_report(run, report):
    baseline, profiled = report['runs']['baseline'], report['runs']['profiled']
    source = Path(report['source'])
    import h5py
    with h5py.File(baseline['python']['hdf5']) as data:
        network = data['VascularNetwork']
        report['stepping'] = {'dt_s': float(network.attrs['dt']),
            'accepted_steps': int(network.attrs['nTSteps']),
            'saved_samples': int(len(network['simulationTime'])),
            'actual_final_time_s': float(network['simulationTime'][-1])}
    stepping = report['stepping']
    f = lambda value: 'not used' if value is None else f'{value:.6g}'
    lines = ['# Bleed / heart-model netlist profiling', '',
        'Status: **'+report['status']+'**.', '',
        f"Source: `{source}`. Original duration: {report['original_duration_s']:g} s; profiled copy: {report['duration_s']:g} s.",
        f"Accepted steps: {stepping['accepted_steps']}; dt: {stepping['dt_s']:.12g} s; final saved time: {stepping['actual_final_time_s']:.12g} s.",
        'The original case and prior outputs were retained. The default run samples several beats,',
        'not the original full 60-second physiological trajectory.', '',
        '## Execution and controller phase', '',
        'C++ uses its persistent Python-2/native worker; NumPy calls the reference solver directly',
        'inside the Starfish process. Benchmark launchers start each simulation in a fresh process;',
        'that isolation is outside normal NumPy netlist communication.', '',
        'Both independent backends use **legacy_post_finalize** controllers for numerical comparability.',
        'Production NumPy now defaults to **iter_init**; these timings compare matching schedules,',
        'not two differently phased trajectories. NumPy still uses the same in-process equations.', '',
        '## Unprofiled timing', '',
        '| Measurement | C++ (s) | NumPy (s) | C++ / NumPy |',
        '| --- | ---: | ---: | ---: |']
    for label, key in (('Starfish solve', 'solve_seconds'), ('Circuit adapter calls, entire case', 'netlist_seconds'),
                       ('Case run including shutdown', 'wall_seconds'), ('Fresh process including imports', 'process_wall_seconds')):
        a, b = baseline['cpp'][key], baseline['python'][key]
        lines.append(f'| {label} | {a:.6f} | {b:.6f} | {a/b:.3f} |')
    lines += ['', 'One unprofiled run per backend, sequentially, with BLAS/OMP thread counts fixed at 1.',
        'Ratios are observations, not repeated benchmark estimates. Circuit adapter time is already',
        'included in solve/case wall time; these rows must not be added.', '',
        '### Circuit adapter operations (unprofiled)', '',
        '| Operation | C++ calls | C++ (s) | NumPy calls | NumPy (s) |',
        '| --- | ---: | ---: | ---: | ---: |']
    for operation in sorted(set(baseline['cpp']['netlist_calls']) | set(baseline['python']['netlist_calls'])):
        a = baseline['cpp']['netlist_calls'].get(operation, {'calls':0,'seconds':0.})
        b = baseline['python']['netlist_calls'].get(operation, {'calls':0,'seconds':0.})
        lines.append(f"| {operation} | {a['calls']} | {a['seconds']:.6f} | {b['calls']} | {b['seconds']:.6f} |")
    lines += ['',
        '| Resource during case run | C++ | NumPy |', '| --- | ---: | ---: |']
    for label, key in (('Starfish CPU seconds', 'starfish_process'), ('Waited worker CPU seconds', 'waited_children')):
        lines.append(f"| {label} | {baseline['cpp']['cpu_seconds'][key]['total']:.6f} | {baseline['python']['cpu_seconds'][key]['total']:.6f} |")
    lines.append(f"| Child processes launched by simulation | {len(baseline['cpp']['launched_children'])} | {len(baseline['python']['launched_children'])} |")
    lines += ['', '![Unprofiled timing and CPU comparison](timing.png)', '',
        '## Worker request measurements', '',
        '| C++ operation | Calls | Total elapsed (s) | Mean (µs) | Maximum (ms) |',
        '| --- | ---: | ---: | ---: | ---: |']
    for operation, row in sorted(baseline['cpp']['worker_requests'].items()):
        lines.append(f"| {operation} | {row['calls']} | {row['seconds']:.6f} | {1e6*row['seconds']/row['calls']:.3f} | {1e3*row['max_seconds']:.3f} |")
    lines += ['', '**Request elapsed time includes native computation, worker scheduling, transport and response waiting.**',
        'It is not a measurement of pure IPC overhead. NumPy makes no worker requests.', '',
        '## Numerical agreement', '',
        '| Output | Maximum absolute NumPy − C++ difference | Unit |', '| --- | ---: | --- |']
    for group, kind, label, unit in (('vessels','pressure','Vessel pressure','Pa'), ('vessels','flow','Vessel flow','m³/s'),
        ('vessels','area','Vessel area','m²'), ('netlist','pressure','Circuit pressure','Pa'),
        ('netlist','flow','Circuit flow','m³/s'), ('netlist','volume','Circuit volume','m³')):
        lines.append(f"| {label} | {f(peak(report['accuracy']['baseline'],group,kind))} | {unit} |")
    lines += ['', 'Every saved vessel P/Q/A and physical netlist P/Q/V column is compared, including initial',
        'rows and sample indices. The report JSON contains tolerances and full per-dataset errors.',
        'The profiled pair and each backend’s profiled-vs-unprofiled outputs are checked separately.', '',
        '## Profiler results', '',
        'Profiles cover the **main-thread solve loop**. Cumulative entries overlap and must not',
        'be summed. Blocking/queue time in the C++ client includes waiting for native work. The',
        'reader thread and native worker call stacks are outside these profiles; child CPU is reported above.', '',
        'C++ uses standard-library `profile.Profile(timer=time.perf_counter)` to keep reader-thread',
        'events out of its call stack; NumPy uses `cProfile.Profile`.',
        'The profilers have different overhead; compare performance using the unprofiled table.', '',
        'Standard-library `profile` excludes much of its dispatcher overhead from attributed function',
        'time. Its attributed totals therefore need not equal measured profiled-run wall time.', '',
        '| Backend | Unprofiled solve (s) | Profiled solve (s) | Profiler slowdown |',
        '| --- | ---: | ---: | ---: |']
    for backend in ('cpp','python'):
        a, b = baseline[backend]['solve_seconds'], profiled[backend]['solve_seconds']
        lines.append(f'| {backend} | {a:.6f} | {b:.6f} | {b/a:.3f} |')
    for backend in ('cpp','python'):
        stats = json.loads((run/'profiled'/backend/'solve_profile.json').read_text())
        lines += ['', '### '+backend, '', '| Function | Calls | Self elapsed (s) | Cumulative elapsed (s) |',
                  '| --- | ---: | ---: | ---: |']
        functions = [row for row in stats['functions'] if row['file'] != 'profile']
        for row in functions[:14]:
            name = Path(row['file']).name+':'+str(row['line'])+' '+row['function']
            lines.append(f"| `{name.replace('|','/')}` | {row['calls']} | {row['self_seconds']:.6f} | {row['cumulative_seconds']:.6f} |")
        lines += ['', f'[Full cumulative/self-time listings](profiled/{backend}/solve_profile.txt) · '
                  f'[Raw pstats data](profiled/{backend}/solve.prof) · [Function JSON](profiled/{backend}/solve_profile.json)']
    if report.get('profile_note'):
        lines += ['', 'Profiler investigation: '+report['profile_note'], '']
    lines += ['', '## Interpretation and limits', '',
        'This measures the complete existing integration, not equal low-level kernels in isolation.',
        'The legacy C++ heart/observer scripts also write diagnostic histories; their NumPy translations',
        'omit those controller-specific files. Both save Starfish and circuit solution histories.',
        'Consequently the measured difference combines communication, solver implementation, controller',
        'API and diagnostic I/O effects. No pure-IPC speedup is inferred from the whole-run ratio.', '',
        'The adapter-operation table identifies where direct calls help and where NumPy still costs',
        'time. Inspect full circuit update/finalization and controller processing as well as coefficient',
        'queries; faster communication does not guarantee every circuit operation is faster.', '',
        '## Reproduce', '', '```bash',
        'python3 -B UnitTesting/profile_netlist_example.py \\',
        '  --case '+shlex.quote(str(source.relative_to(ROOT) if source.is_relative_to(ROOT) else source))+' \\',
        '  --duration '+str(report['duration_s']), '```', '',
        'Each invocation allocates a new `results_netlist_profile/run_NNN/` beside the case.',
        'Use `python3 -m pstats <path>/solve.prof`, then `sort cumulative` and `stats 30`,',
        'or open the raw profile in a compatible viewer. See `comparison.json` for provenance.', '']
    (run/'comparison.md').write_text('\n'.join(lines))


def main():
    from UnitTesting.run_example_netlist_comparisons import snapshot, run_backend, compare_outputs, save_json, RTOL, ATOL
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, default=ROOT/'examples/cr_sf_tutorial_demo/heart_model/input.xml')
    parser.add_argument('--duration', type=float, default=5.)
    args = parser.parse_args()
    source = args.case.expanduser().resolve()
    if not source.is_file():
        parser.error('case must name an existing runnable network XML')
    if not 0. < args.duration < float('inf'):
        parser.error('duration must be finite and positive')
    output = source.parent/'results_netlist_profile'
    output.mkdir(exist_ok=True)
    index = 1
    while (output/f'run_{index:03d}').exists():
        index += 1
    run = output/f'run_{index:03d}'
    run.mkdir()
    copied, hashes = snapshot(source, run/'inputs')
    tree = ET.parse(copied)
    original = float(tree.findtext('./simulationContext/totalTime'))
    tree.find('./simulationContext/totalTime').text = str(args.duration)
    tree.find('./simulationContext/timeSaveBegin').text = '0.0'
    tree.write(copied, encoding='utf-8', xml_declaration=True)
    report = {'source': str(source), 'original_duration_s': original, 'duration_s': args.duration,
        'source_sha256': hashes, 'snapshot_input_sha256': hashlib.sha256(copied.read_bytes()).hexdigest(),
        'rtol': RTOL, 'atol': ATOL, 'runs': {}, 'accuracy': {}, 'status': 'running',
        'controller_phase': 'legacy_post_finalize; production default is iter_init'}
    from UtilityLib.netlistPyAdapter import netlist_source_directory
    import numpy as np
    report['provenance'] = {'python': sys.version, 'numpy': np.__version__,
        'netlist_py': str(netlist_source_directory()),
        'sha256': {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (
            Path(__file__).resolve(), ROOT/'UnitTesting/run_example_netlist_comparisons.py',
            ROOT/'UtilityLib/netlistPyAdapter.py', ROOT/'ext/build/crimson_netlist_worker',
            netlist_source_directory()/'NetlistCircuit_reference.py')},
        'threads': {'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}}
    print('Results: '+str(run), flush=True)
    try:
        for mode in ('baseline','profiled'):
            folder = run/mode
            folder.mkdir()
            report['runs'][mode] = {}
            for backend in ('cpp','python'):
                print(f'START {mode} {backend}', flush=True)
                result = run_backend(copied, backend, folder, profile=(mode=='profiled'), diagnostics=True)
                report['runs'][mode][backend] = result
                save_json(run/'comparison.json', report)
                if result['status'] != 'completed':
                    raise RuntimeError(f"{mode} {backend} failed: {result.get('error')}; see {result['console_log']}")
                print(f"DONE {mode} {backend}: solve {result['solve_seconds']:.3f} s", flush=True)
            report['accuracy'][mode] = compare_outputs(report['runs'][mode]['cpp'], report['runs'][mode]['python'])
        for backend in ('cpp','python'):
            report['accuracy']['profiling_invariance_'+backend] = compare_outputs(
                report['runs']['baseline'][backend], report['runs']['profiled'][backend])
        report['status'] = 'passed' if all(row['passed'] for row in report['accuracy'].values()) else 'failed_accuracy'
        chart(run, report['runs']['baseline'])
        write_report(run, report)
    except Exception as error:
        report.update(status='failed', error=str(error))
        (run/'comparison.md').write_text('# Netlist profiling\n\nFailed: '+str(error)+'\n')
        raise
    finally:
        save_json(run/'comparison.json', report)
    print('Report: '+str(run/'comparison.md'), flush=True)
    raise SystemExit(0 if report['status']=='passed' else 1)


if __name__ == '__main__':
    main()
