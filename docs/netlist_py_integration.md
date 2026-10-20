# CRIMSON netlist_py integration

STARFiSh now uses the standalone CRIMSON NumPy/reference implementation for
real Netlist boundaries. The backend is hardcoded; production does not import
JAX, start the C++ worker, or create a generated 0D replacement domain.

## Configuration and use

Edit the single location setting in [../netlist_config.py](../netlist_config.py):

```python
NETLIST_PY_DIRECTORY = "~/crimson/cfs_reg/CRIMSONFlowsolver/flowsolver/netlist_py"
```

The repository directory and its `src` directory both work. Relative paths
resolve against the STARFiSh root containing the configuration file, not the
case directory. A missing or mixed source checkout raises an explicit error;
restart the Python process after changing checkout locations.

Continue using the existing case layout and solver command:

```text
my_case/
    input.xml
    netlist_surfaces.xml
    inflow.csv                         if used by the case
    myController_reference.py          if declared by a custom control
```

```bash
python3 /home/sadid/starfish/solver.py /path/to/my_case/input.xml -o /path/to/results
```

The usual `results/SolutionData_<number>/` receives STARFiSh HDF5/XML and
`netlistPressures_surface_<id>.dat`, `netlistFlows_surface_<id>.dat`, and
`netlistVolumes_surface_<id>.dat`. Surface ID 0 is preserved. The `.dat`
tables contain the initial state at row 0 and one row per accepted timestep,
with physical node/component columns and an integer timestep column. Text
spacing can differ from C++; parsed columns and precision remain compatible.

The adapter imports reference modules directly from the configured checkout.
The recorded validation environment is Python 3.13.9 / NumPy 2.4.0. The upstream
package declares Python 3.14 as its installation target; these source-import
checks do not constitute a clean Python 3.14 packaging validation.

## Implementation and retained C++ integration

`NetworkLib/netlistManager.py::_get_adapter()` constructs
`UtilityLib/netlistPyAdapter.py::NetlistPyAdapter`. The old C++ import,
construction and loading calls are commented immediately above the new call.
The old adapter, transport client, C++ runtime/worker/binding sources, build
files and existing validation checks have been retained unchanged.

The new adapter resolves circuit equations, mode selection and state acceptance
through `BoundaryConditionManager_reference`, `NetlistCircuit_reference` and
the existing reference controller modules in netlist_py. STARFiSh still owns
its vessel solver and characteristic equations in `NetworkLib/netlistInterface.py`.

Existing mapping is intentionally preserved: sorted registered physical surface
IDs map to XML `circuitIndex` 1..N. The mapping is stored in `surface_to_circuit`
and logged. Circuit counts and indices must match exactly. Repeated registration
of the same endpoint is allowed; conflicting vessel/endpoint ownership fails.
The STARFiSh external `flowSign` and the circuit's internal component orientation
remain separate. The adapter performs no implicit pressure/flow unit conversion:
STARFiSh cases and their controller constants must be consistent in Pa, m^3/s,
and m^3. Archived validation fixtures retain their own consistent native units.

## Accepted-state and controller behavior

1. Initialize circuit modes once for the timestep.
2. Probe affine `P = dp_dq * Q + Hop` coefficients without accepting histories.
3. Solve the STARFiSh endpoint characteristic, or impose zero flow for a blocked diode.
4. Collect every surface's final pressure and flow.
5. Solve all circuit updates using full `dt` and the active input at each port.
6. Publish physical pressure/flow/volume and accept histories once.
7. Update controller targets for the following timestep.

This preserves the **post-finalization controller phase of STARFiSh's existing
C++ worker**. It deliberately differs from the upstream standalone ordinary
0D driver's pre-solve controller call site. Built-in LV control also assigns
its fresh-run E(0) target during loading, matching the C++ constructor, without
advancing controller time. Alpha-step probes and full-step acceptance are kept
separate; the production STARFiSh setting remains `alfi=1`.

Modern custom XML control source `foo` requires case-local `foo_reference.py`
with the upstream reference ControllerProgram contract, API version and priority.
Legacy `foo.py` remains available for C++ comparison and is not executed by the
new runtime. The supplied `examples/bifurcation_heart_netlist` case now includes
its NumPy heart controller alongside the retained legacy script. Its SI constants,
piecewise cosine law and phase advancement match the old script; legacy diagnostic
file IO is omitted. Other legacy custom controllers require their own modern
reference translation. Built-in LV and bleed controls are supported.

Close writes only initial and accepted states; it never commits a partially
completed timestep. Solver cleanup resets the process-wide manager between runs.
Repeated coefficient probes, duplicate finalization, missing surface updates,
changed dt, invalid values and configuration failures have focused checks.

## Validation against the current C++ worker

Results are recorded in [netlist_py_validation_results.json](netlist_py_validation_results.json).
Raw artifacts from this run are in `/tmp/starfish-netlist-validation-final/`:
each case has both backends' histories, replay traces or full solver output.

The comparison imports the retained C++ adapter explicitly in validation code.
For complete STARFiSh runs, a temporary substitution chooses that adapter only
inside the validation process; production selection remains hardcoded to NumPy.
Both backends receive identical XML, initial conditions, physical input sequences,
timestep, alpha value and surface mapping. Full 1D cases use the existing inlet
CSV or heart law and compare every saved vessel P/Q/A dataset plus all netlist
pressure/flow/volume histories. Expected accepted row counts are checked.

Fifteen comparisons passed:

| Comparison | Accepted steps | Result |
| --- | ---: | --- |
| Resistor, surface 0 | 64 | PASS |
| Reversed interface component | 64 | PASS |
| SI RCR | 64 | PASS |
| SI RCR with alpha 0.6 | 64 | PASS |
| Multiple SI RCR surfaces, nonconsecutive IDs | 64 | PASS |
| Mixed resistor/capacitor/inductor/fixed-flow branches | 64 | PASS |
| Diodes with repeated blocking/reopening and flow reversal | 64 | PASS, diagnostic difference below |
| Pressure chambers and built-in LV controller | 64 | PASS |
| Plain volume trackers | 64 | PASS |
| Built-in bleed controller, including its timed trigger | 1604 | PASS |
| Paired legacy/modern doubling-resistance controller | 8 | PASS |
| Full single-vessel resistor, 1 s | 474 | PASS |
| Full single-vessel RCR, 1 s | 474 | PASS |
| Full bifurcation with RCR outlets, 1 s | 459 | PASS |
| Full heart-driven vessel case, 1 s (heart period 0.86 s) | 448 | PASS |

The four complete 1D comparisons had zero maximum difference in their saved
vessel P/Q/A arrays. The heart case's netlist pressure-history difference was
approximately 1.00e-11 Pa, its netlist flow difference approximately 1.08e-19 m^3/s,
and its volume difference zero. These statements apply to these runs, not a
general bitwise-equivalence claim.

Comparisons enforce `rtol=5e-11`, with absolute tolerances of `1e-8` for pressure,
`1e-12` for flow/volume, `1e-14` for vessel area, and `1e-6` for affine slopes.
Units follow the declared case convention; archived fixture quantities must not
be relabelled as physiological SI measurements.

One diagnostic differs: `CircuitData.cxx::boundaryConditionTypeHasJustChanged()`
resets its flag and returns the reset value. NumPy reports the real transition.
The three-port diode comparison recorded 48 such diagnostic differences while
the actual interface modes, event sequence and physical histories agreed.
STARFiSh's characteristic interface already discards this diagnostic. The old
C++ implementation was preserved; its flag behavior was not copied into NumPy.

Run the focused coupling checks:

```bash
python3 -B -m unittest discover -s UnitTesting -p test_netlist_py_adapter.py -v
```

Seven tests passed, covering lifecycle/failure handling, controller timing and
initialization, surface ownership, surface-0 output, process reset, configured
source resolution, and a fresh-process check that NumPy loading imports neither
JAX nor the C++ adapter.

Reproduce the C++ comparison with a fresh output directory:

```bash
python3 -B UnitTesting/validate_netlist_backends.py \
    --output-dir /tmp/starfish-netlist-comparison-new
```

This requires the retained `ext/build/crimson_netlist_worker`, its legacy runtime
dependencies, the example cases in this workspace and the configured netlist_py
checkout's validation fixtures. These dependencies belong to comparison work;
normal NumPy simulations do not load the C++ worker or its libraries.

## Current integration limits

This adapter supports independent boundary circuits, including supported modern
controllers and automatic diode modes. A shared downstream netlist requires
coupled endpoint response handling and is explicitly rejected. A general
pressure-driven port returning nonzero flow also needs a different boundary
equation; this path verifies the diode-blocked zero-flow condition instead.
Long physiological settling, arbitrary controller combinations and full Starfish
JAX compilation are not established by these regression checks. No upstream
netlist_py source files were modified for this integration.
