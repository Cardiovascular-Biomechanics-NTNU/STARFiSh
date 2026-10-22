# 1D netlist lifecycle validation

Status: **passed**.

Production uses prepare/controllers → observational trials → publish/accept → output/rollover.

37 unit checks; 15 historical C++ comparisons.

Regular controls matched the upstream ZeroDDriver for 10 steps, including the first update.
An additional 24-step RCR feedback trajectory matched accepted histories and owner observations exactly.
Controlled closed-loop states matched upstream exactly for 40 steps, including shared broadcasts,
chamber E/V0, fixed pressure, inductor/capacitor histories, and diode mode changes.

| Complete 1D case | Max vessel ΔP (Pa) | Max vessel ΔQ (m³/s) | C++ solve (s) | NumPy solve (s) |
| --- | ---: | ---: | ---: | ---: |
| closed_loop_passive | 1.09139e-11 | 1.65426e-18 | 0.488121 | 0.370277 |
| closed_loop_controlled | 1.27329e-11 | 1.31798e-18 | 0.490397 | 0.427382 |

Both complete cases use the same simultaneous 1D coupling in native C++ and NumPy.
The controlled case uses native upstream/downstream controllers at iter_init.
Timings are single-run measurements including IPC; not repeated benchmarks.

The independent historical C++ worker still uses post-finalize controllers. Its 15 comparisons
explicitly select the matching legacy NumPy profile; they do not compare different phases.
All eight retained old C++ integration files are byte-identical to HEAD.

The generated 0D replacement has a different delayed domain exchange. This report establishes
the tested circuit/controller lifecycle under matching ports, not identical 0D/1D trajectories.

Complete test names, per-case report paths, versions and source/binary hashes: [validation JSON](netlist_1d_lifecycle_validation_results.json).

## Per-case accuracy and timing

- [closed_loop_passive](../examples/closed_loop_passive/results_netlist_comparison/main_006/comparison.md)
- [closed_loop_controlled](../examples/closed_loop_controlled/results_netlist_comparison/main_003/comparison.md)
