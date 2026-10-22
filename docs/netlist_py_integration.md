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

`NetworkLib/netlistDriver.py::OneDDriver` owns the common host lifecycle for
regular and closed-loop runs. `FlowSolver` executes:

```text
iter_init(n, t_n, dt)
    initialize circuits and modes from accepted valves
    gather previous published owner-local p/q/V
    update the shared controller schedule once; apply targets
iter_step(advance_domain)
    observational coefficients / full cross-port response
    characteristic endpoint solve and vessel/connection operations
    stage complete circuit input/candidate; no history acceptance
iter_finalize()
    full-dt circuit update and physical publication
    accept current histories and retain next diode flags
    retain prepared controller state/targets
network output callback
runtime memory rollover
```

The production controller phase is **pre-solve `iter_init`**, matching upstream
`ZeroDDriver`. The first step uses the first controller update, rather than
waiting until the end of that step. Initial observations and historical state
remain separate; initial setup is not an equilibrium solve. The driver keeps
start time `t_n` distinct from endpoint timestamp `t_n + dt`. Repeated probes
reuse one preparation. Full-step circuit acceptance precedes output and memory
rollover for both paths. A failed preparation/domain step cannot be retried or
accepted through the same driver. Timesteps use fixed positive dt.

The independent mutable adapter installs controller state during preparation,
as upstream mutable `ZeroDDriver` does. Closed-loop preparation is functional:
proposed controllers and targets stay in `prepared` until acceptance, exactly
as upstream `controlled_closed_loop_iter_init/step/finalize` does. That does not
move their mathematical update time after the solve.

The retained independent C++ worker still uses post-finalization controllers.
`controller_phase="legacy_post_finalize"` is an explicit historical NumPy
compatibility profile, selected only by the old-backend comparison tools.
It is not the production default. Older parity tables below used that profile;
they do not establish equality between different controller phases. Built-in
LV loading still assigns E(0) without advancing time; production then updates
it once in the first `iter_init`. Alpha probes and full-dt acceptance remain
separate; production uses `alfi=1`.

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

## Closed-loop integration

Starfish now detects a nonempty case-local `netlist_closed_loop_downstream.xml`
and selects `UtilityLib/netlistClosedLoopPyAdapter.py`. It uses the existing
reference subsection assembler and state acceptance in netlist-py. It does not
create a generated 0D replacement of the Starfish vessels.

`NetworkLib/netlistCoupling.py` solves the connected vessel characteristics
simultaneously, retaining the full cross-port pressure/flow responses. It
supports the all-flow equation and the general mixed pressure/flow equation
derived in the [implementation plan](netlist_closed_loop_implementation_plan.md).
The boundary group copies each endpoint's characteristic transform before
preparing other endpoints, validates every proposed P/Q/A result, then scatters
the endpoint values. The circuit candidate is accepted once after the physical
numerical operations and before network output and runtime memory rollover.

Physical surface IDs, including 0, are mapped explicitly to the positive IDs
required by the upstream closed-loop setup. A private downstream XML copy is
normalized; original XML is retained. Output uses the physical surface labels
and `netlist{Pressures,Flows,Volumes}_downstreamCircuit_0.dat`. The output folder
`netlist_closed_loop_inputs/` includes original/normalized XML, endpoint bindings,
source hashes, dt and accepted step count.

The first supported profile requires:

- One downstream circuit with XML `circuitIndex=1`.
- Connected return surfaces plus independent loss outlets. Independent circuits
  retain square local blocks and do not receive artificial return junctions.
- Supported upstream/reference controllers or static targets, `alfi=1`, and history write interval 1.
- `ConstantPressure` vessel initialization and `MacCormack_Flux`.
- No Type 1 prescription at a grouped endpoint, separate `venousPool`, or cycle mode.

Closed-loop XML controls are parsed with the upstream manifest and one shared
upstream/downstream schedule. Sources are snapshotted before trusted modern
programs load. Python priority, progressive first-writer-wins broadcasts,
built-ins, owner observations and distinct target binding follow upstream.
The production adapter directly calls `controlled_closed_loop_iter_init`,
`controlled_closed_loop_iter_step` and `controlled_closed_loop_iter_finalize`.
The same prepared state supplies every probe and full update. Finalization
publishes chamber `E*(V-V0)` and fixed pressures before accepting history and
determining next diode flags. No generated replacement domain is constructed.

Supported targets are those of the upstream manifest: component parameters,
fixed nodal pressures and chamber unstressed volume; target collisions fail.
Built-in LV and bleed controls use the upstream programs. The modern closed-loop
fixture checks shared broadcasts, LV E/V0, fixed pressure, inductor/capacitor
history and changing diode modes against upstream states exactly. This does
not establish an arbitrary controlled physiological trajectory or long-time
stability.

### Runnable passive closed circulation

Tracked inputs are in `ext/tests/closed_loop_passive/`; an organized copy and
all comparison/refinement results are in `examples/closed_loop_passive/`.
The fixture is a 0.5 m vessel with proximal surface 0 (`flowSign=-1`) and
distal surface 4 (`flowSign=1`). Each port has R=1e7 Pa·s/m³. The return has
R=1e8 Pa·s/m³ and C=2e-9 m³/Pa. Vessel initial pressure is 10000 Pa, return
initial pressure 8000 Pa. It has no pump, prescribed inflow or bleed: its
startup transient comes from these explicitly specified initial conditions.

```bash
python3 -B solver.py examples/closed_loop_passive/input.xml \
    -o examples/closed_loop_passive/results_new
```

### Closed-loop C++ validation

The existing C++ worker remains available unchanged and still constructs
independent circuits. A separate optional target executes native shared-return
circuits for validation:

```bash
cmake -S ext -B ext/build
cmake --build ext/build --target crimson_closed_loop_validation_worker -j2

python3 -B -m unittest discover -s UnitTesting -p test_netlist_closed_loop.py -v
python3 -B UnitTesting/validate_closed_loop_backends.py
```

`ext/ClosedLoopValidationWorker.cpp` uses the native CRIMSON subsection classes.
`UnitTesting/closed_loop_cpp_reference.py` adapts its actual native responses and
physical observations to the same Starfish simultaneous boundary schedule.
NumPy topology/identity records are shared setup, but C++ owns its numerical
solves and histories. A check replaces the NumPy circuit solve with an exception
while exercising the C++ backend, to detect accidental fallback.

The native source has a one-shot stored-flow RHS guard at initialization and
when an initially blocked port first becomes flow-driven. The validation worker
performs a zero-flow setup probe and repeats each frozen query with cache
invalidation, without publication or acceptance, so the reported response uses
the requested port inputs. This compatibility handling is recorded in the
validation provenance. It does not alter the preserved C++ source or advance
controllers/valves during probes.

The example runner now explicitly selects this C++ backend for closed-loop
comparisons; its recorded adapter class identifies which backend actually ran.
The separate validation worker registers upstream and downstream controls in
one native `ControlSystemsManager` and updates it once at START, after circuit
initialization and before queries. It never updates controls during probes or
acceptance. Paired legacy `.py` scripts are required for a controlled native
comparison; production executes only the modern `_reference.py` programs.
Comparisons use fresh processes, fixed single-thread settings and private input
snapshots. Timings include IPC, native repeated probes and common output; they
are single-run integration observations, not isolated circuit benchmarks.

The validation helper writes per-case accuracy/timing and conservation reports,
then repeats the NumPy example at 80 and 160 vessel nodes. Shared KCL and
pressure equalities, capacitor history, and endpoint matching are checked
separately from the total-volume defect of the existing 1D discretization.
Space and time refine together at fixed CFL; this is not an independent
measurement of spatial or temporal convergence order.

Recorded implementation evidence is in
[netlist_closed_loop_validation_results.json](netlist_closed_loop_validation_results.json).
The final run passed 27 unit checks and all 15 existing independent-backend
comparisons. The full passive closed-loop case accepted 112 steps, with a
two-sample runtime buffer, and compared every saved vessel P/Q/A and circuit
pressure/flow/volume column. Maximum vessel pressure difference was about
1.1e-11 Pa and flow difference about 1.7e-18 m³/s. Shared KCL residual was about
3.1e-19 m³/s. The maximum total-volume defect decreased from 1.36e-7 to 7.40e-8
to 3.87e-8 m³ for 40/80/160 nodes at fixed CFL. These are results for this
specified passive transient; they do not establish controlled-heart parity.

Repeat use of an occupied closed-loop solution directory is rejected before
the existing histories or HDF5/XML can be replaced. Select a new output
directory or data number. Original case XML is snapshotted when loading, so
the saved source hashes identify the inputs actually used by the adapter.

## Current integration limits

This adapter supports independent boundary circuits, including supported modern
controllers and automatic diode modes. The independent adapter's scalar path
retains its diode-blocked zero-flow condition. Shared downstream cases use the
dedicated simultaneous path described above and its narrower initialization profile.
The proposed equations, implementation phases and C++ validation strategy are
documented in the separate [closed-loop implementation plan](netlist_closed_loop_implementation_plan.md).
Long physiological settling, arbitrary controller combinations and full Starfish
JAX compilation are not established by these regression checks. No upstream
netlist_py source files were modified for this integration.

## 1D driver lifecycle verification

Run all checks and save a new report directory:

```bash
python3 -B UnitTesting/validate_netlist_driver.py \
    --output-dir /tmp/starfish-driver-validation-new
```

The [recorded report](netlist_1d_lifecycle_validation_results.md) and
[machine-readable evidence](netlist_1d_lifecycle_validation_results.json) include:

- Direct regular controller/state comparison with upstream `ZeroDDriver`,
  including first-step update, three probes per step, target refresh and a
  24-step pressure/flow feedback RCR trajectory with accepted capacitor history.
- Exact full-state comparison with upstream controlled closed-loop stages for
  40 steps: trial matrices/RHS/solutions, controllers, targets, physical
  publication, history, accepted count, time, valves and changing modes.
- Complete regular and controlled closed-loop 1D runs checking preparation
  before domain operations and acceptance before output under memory rollover.
- Native C++ response/history comparisons with passive and controlled circuits,
  plus complete passive/controlled 1D accuracy and timing reports.
- Historical independent C++ comparisons using an explicitly matching legacy
  controller phase, and byte-identity checks of eight retained old integration files.

The controlled example is `examples/closed_loop_controlled/`, with tracked
inputs in `ext/tests/closed_loop_controlled/`. Its priority-0 downstream producer
reads previous owner pressure and broadcasts to the priority-1 upstream
consumer; both affect the first solve. Results and per-case timing/accuracy
notes remain inside each example directory.

**Identity boundary:** these checks establish the tested circuit/controller
lifecycle for matching ports. Starfish retains simultaneous 1D characteristic
coupling. Upstream generated 0D replacement exchange deliberately retains
delayed published/manager port snapshots. Different domain equations and
exchange schedules do not produce identical autonomous 0D and 1D trajectories.

## Profile the blood-loss heart example

```bash
python3 -B UnitTesting/profile_netlist_example.py \
    --case examples/cr_sf_tutorial_demo/heart_model/input.xml \
    --duration 5
```

The profiler allocates `results_netlist_profile/run_NNN/` beside the example.
It snapshots the source, changes only the copied simulation duration/save
start, and runs C++ then NumPy in fresh, sequential processes with one BLAS/OMP
thread. Each backend gets an unprofiled timing run and a separate deterministic
solve-loop profile. C++ uses `profile.Profile(timer=time.perf_counter)` for a
thread-local stack; NumPy uses `cProfile.Profile`. The report verifies that profiling did
not change either backend's saved physical outputs.

`comparison.md/json` contain timing, CPU use, worker request counts/durations,
accuracy and provenance. `timing.png/svg` visualize unprofiled measurements.
`profiled/{cpp,python}/solve.prof`, `solve_profile.txt` and `solve_profile.json`
provide raw profiles and cumulative/self-time function listings.

Independent NumPy uses the explicit historical controller phase to match the
retained C++ worker. Production remains pre-solve. The legacy controllers also
write diagnostic histories that the NumPy translations omit; that I/O difference
is retained and stated in the report. End-to-end timing therefore includes
backend, transport, controller API and diagnostic I/O effects.

The profilers attribute main-thread elapsed time, including response waits; they
cannot inspect native functions or the C++ worker's Python-2 interpreter. The
report separately measures waited-child CPU. Worker request elapsed time
includes computation and scheduling, so it must not be called pure IPC cost.
The per-simulation child-process log verifies that the NumPy run launches no
netlist worker. Fresh processes used by the benchmark launcher are isolation
for the comparison, not NumPy netlist communication.

## Heart-driven 1D closed loop with blood loss

`examples/closed_loop_blood_loss_heart/` is a separate adaptation of the existing
SI blood-loss vessel tree. It joins the systemic tails and valved heart inlet
through the supplied `05-HeartModel-ClosedLoop` venous return circuit, converted
from mm³ to m³ units. The hemorrhage circuit remains an independent external
drain. All connected and independent ports share the characteristic solve and
one controller schedule; the 1D vessels replace the source generated 0D domain.

Reproduction and model/monitor definitions are in
[`ext/tests/closed_loop_heart/README.md`](../ext/tests/closed_loop_heart/README.md).
`UnitTesting/build_closed_loop_heart.py` creates a new case without changing the
sources. `UnitTesting/run_closed_loop_heart.py` runs native C++ then NumPy and
saves actual backend controller traces, all physical histories, pressure/flow/
volume/heart-rate/lost-volume monitors, PNG/PDF plots, accuracy and timing notes.

The completed 60-second run and its limitations are documented in
[`netlist_closed_loop_heart_validation_results.md`](netlist_closed_loop_heart_validation_results.md).
Both backends completed; the retained strict comparison thresholds were exceeded
by small pressure/elastance differences. A material storage-plus-loss defect was
localized to the 1D vessel volume/endpoint-flow balance. Local circuit checks and
39 regression tests passed. This result does not establish whole-system volume
conservation.
