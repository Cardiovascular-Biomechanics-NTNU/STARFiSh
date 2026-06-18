# Netlist 1D Coupling Plan

This note defines the first coupling target between the STARFiSh 1D solver and
the CRIMSON netlist boundary-condition machinery.

The first user-facing boundary condition should be named simply:

```xml
<_Netlist>
  <surfaceId>0</surfaceId>
</_Netlist>
```

The real netlist circuit description is not parsed by STARFiSh. It remains a
CRIMSON netlist input file and is handled by CRIMSON's own netlist XML reader.
The STARFiSh XML only maps a 1D vessel boundary to a netlist surface. The
netlist file name is intentionally fixed:

```text
netlist_surfaces.xml
```

and that file must live in the same case directory as STARFiSh `input.xml`.

For early testing, `_Netlist` may also support a temporary constant-coefficient
mode:

```xml
<_Netlist>
  <surfaceId>0</surfaceId>
  <Rtilde unit="Pa s m-3">133320000.0</Rtilde>
  <S unit="Pa">0.0</S>
  <flowSign>1</flowSign>
</_Netlist>
```

This fake mode lets us verify the 1D characteristic coupling before calling the
C++ netlist.

Internally, the coupling law is the Robin pressure-flow condition:

```text
P = Rtilde * Q + S
```

This matches the CRIMSON netlist interface form:

```text
P = Q * R~ + S
```

where:

- `P` is the interface pressure.
- `Q` is the interface flow.
- `Rtilde` / `R~` / `dp_dq` is the effective pressure-flow slope.
- `S` / `Hop` is the pressure shift from history, sources, capacitors, and
  other netlist state.

## Current Implementation Map

The coupling now has three layers:

```text
STARFiSh XML + Type 2 BC
  -> Python interface/manager
  -> CRIMSON C++ netlist bridge
```

The main rule is that STARFiSh owns the 1D solver and characteristic update,
while CRIMSON owns the netlist circuit solve.

### Files Added or Extended

```text
NetworkLib/classBoundaryConditions.py
```

Adds the STARFiSh Type 2 boundary condition:

```python
class Netlist(BoundaryConditionType2)
```

Responsibilities:

- receives XML fields already parsed by STARFiSh:
  `surfaceId`, plus optional `flowSign`, `Rtilde`, `S`
- registers the boundary with `NetlistBoundaryManager`
- creates `NetlistBoundaryInterface`
- delegates each solver boundary call to the interface layer

Important methods:

```python
Netlist.initialize()
Netlist.setPosition(position)
Netlist.funcPos0(...)
Netlist.funcPos1(...)
```

`funcPos0` is the proximal/inlet-side handler and `funcPos1` is the
distal/outlet-side handler. Both call the same interface object; the interface
uses `position` to select the correct characteristic direction.

```text
NetworkLib/netlistInterface.py
```

Owns the 1D mathematical coupling.

Important functions:

```python
solve_robin_characteristic(
    position,
    omega_known,
    R,
    P,
    Q,
    dp_dq,
    hop,
    flow_sign=1.0)

solve_prescribed_flow_characteristic(
    position,
    omega_known,
    R,
    Q,
    prescribed_flow=0.0)
```

This solves the unknown characteristic from:

```text
P_new = dp_dq * (flow_sign * Q_new) + hop
```

and:

```text
[dP, dQ]^T = R_char * omega
```

Important class:

```python
class NetlistBoundaryInterface
```

Responsibilities:

- asks the manager for `(dp_dq, Hop)`
- solves the unknown characteristic
- computes `du = [dP, dQ]`
- records final interface pressure/flow back into the manager

Important method:

```python
NetlistBoundaryInterface.solve(...)
```

This is the main call path from STARFiSh into the netlist coupling.

```text
NetworkLib/netlistManager.py
```

Owns boundary registration and chooses where coefficients come from.

Important class:

```python
class NetlistBoundaryManager
```

Responsibilities:

- stores all registered netlist boundaries by `surfaceId`
- owns one global netlist file for the whole case:

  ```text
  <case directory>/netlist_surfaces.xml
  ```

  This matches CRIMSON's `numNetlistLPNSrfs` / `indicesOfNetlistSurfaces(k)`
  model: one file contains all outlet circuits, while each STARFiSh boundary
  only says which `surfaceId` it maps to.

- supports fake constant mode for quick tests:

  ```text
  Rtilde != None -> return (Rtilde, S)
  ```

- supports real CRIMSON mode:

  ```text
  Rtilde == None -> call CrimsonNetlistAdapter
  ```

- records final `(P, Q)` after the 1D characteristic solve
- forwards final state to CRIMSON in real mode
- finalizes the one loaded adapter once per timestep when called

Important methods:

```python
set_output_directory(...)
register_boundary(...)
compute_coefficients(...)
compute_update_coefficients(...)
flow_permitted(...)
start_timestep(...)
record_boundary_state(...)
finalize_timestep(...)
```

```text
UtilityLib/crimsonNetlistAdapter.py
```

Python adapter around the compiled CRIMSON bridge.

Important class:

```python
class CrimsonNetlistAdapter
```

Responsibilities:

- imports the compiled module `crimson_starfish_bridge`
- constructs `CrimsonBridge(hstep, alfi, delt)`
- loads the CRIMSON netlist XML
- calls CRIMSON for `(dp_dq, Hop)`
- pushes final `(P, Q)` back to CRIMSON

Important methods:

```python
set_output_directory(...)
register_surfaces(...)
load(dt=None)
compute_implicit_coefficients(surface_id, timestep, time, dt, flow)
compute_update_coefficients(surface_id, timestep, time, dt, flow)
flow_permitted(surface_id, dt=None)
boundary_condition_type_changed(surface_id, dt=None)
start_timestep(timestep, time, dt)
update_state(surface_id, timestep, time, dt, pressure, flow)
finalize_timestep(timestep)
```

Current practical note:

CRIMSON's XML reader still assumes `netlist_surfaces.xml` can be opened from
the current working directory. The adapter temporarily changes directory to the
XML file directory during `load()` so local case folders work.

```text
ext/StarfishBridge.cpp
```

C++ bridge between Python and CRIMSON's `NetlistCircuit`.

Important class:

```cpp
class StarfishBridge
```

Responsibilities:

- initializes PETSc if needed
- owns one `NetlistCircuit`
- owns scalar pressure/flow values whose addresses are passed into CRIMSON
- loads the CRIMSON netlist file
- returns CRIMSON's affine pressure-flow law:

  ```text
  (dp_dq, Hop)
  ```

Important methods:

```cpp
void load(const std::string& xml_path);
void load(const std::string& xml_path, const std::vector<int>& surface_ids);
void register_surfaces(const std::vector<int>& surface_ids);
void set_output_directory(const std::string& output_directory);
std::pair<double, double> compute_implicit_coefficients(
    int surface_id,
    int timestep,
    double time,
    double dt,
    double flow);
std::pair<double, double> compute_update_coefficients(
    int surface_id,
    int timestep,
    double time,
    double dt,
    double flow);
bool flow_permitted(int surface_id);
bool boundary_condition_type_changed(int surface_id);
void update_state(
    int surface_id,
    int timestep,
    double time,
    double dt,
    double pressure,
    double flow);
void start_timestep(int timestep, double time, double dt);
void finalize_timestep(int timestep);
```

Current call sequence inside `load()`:

```cpp
setNetlistXmlFileName(xml_path)
setPressureAndFlowPointers(&pressure, &flow)
createCircuitDescription()
closeAllDiodes()
detectWhetherClosedDiodesStopAllFlowAt3DInterface()
initialiseCircuit()
```

```text
ext/bindings.cpp
```

Nanobind module definition.

Python-visible class:

```python
crimson_starfish_bridge.CrimsonBridge
```

Bound methods:

```python
load(...)
register_surfaces(...)
set_output_directory(...)
start_timestep(...)
compute_implicit_coefficients(...)
compute_update_coefficients(...)
flow_permitted(...)
boundary_condition_type_changed(...)
update_state(...)
finalize_timestep(...)
```

```text
ext/verify_bridge.py
```

Small verification script. It loads:

```text
examples/baseline_netlist_from_xml/netlist_surfaces.xml
```

and checks that the bridge returns coefficients from CRIMSON.

```text
UtilityLib/networkXml043.py
UtilityLib/constants.py
```

XML registration layer.

Responsibilities:

- make `Netlist` and `_Netlist` visible in STARFiSh `input.xml`
- define fields:

  ```text
  surfaceId
  flowSign  optional, defaults to 1
  Rtilde    optional, defaults to None
  S         optional, defaults to 0
  ```

`Rtilde` and `S` are allowed to be `None` so the same XML structure can run in
real CRIMSON mode.

```text
NetworkLib/classVascularNetwork.py
```

Currently has a small compatibility update so fake constant `_Netlist` cases
can participate in resistance estimation when `Rtilde` is provided.

Open cleanup:

Real adapter mode with `Rtilde=None` still cannot provide an initial resistance
estimate to STARFiSh during initialization. The solver can run, but STARFiSh
prints its fallback resistance message. A later cleanup should let the manager
query CRIMSON once during initialization or provide an optional initialization
resistance.

## Data Flow Schematic

Current implemented flow:

```text
STARFiSh input.xml
  |
  |  vesselId, boundary position, surfaceId,
  |  flowSign, optional Rtilde/S
  v
classBoundaryConditions.Netlist
  |
  |  P, Q, known omega, R_char, n, dt
  v
NetworkLib.netlistInterface.NetlistBoundaryInterface
  |
  |  asks for coefficients:
  |  surfaceId, timestep, time, dt, pressure, signed flow
  v
NetworkLib.netlistManager.NetlistBoundaryManager
  |        |
  |        | fake mode: Rtilde/S from input.xml
  |        |
  |        | real mode: call Python adapter
  v
UtilityLib.crimsonNetlistAdapter.CrimsonNetlistAdapter
  |
  |  import nanobind module and call bridge
  v
ext.crimson_starfish_bridge.CrimsonBridge
  |
  |  C++ StarfishBridge -> CRIMSON NetlistCircuit
  |
  |  CRIMSON parses netlist_surfaces.xml and solves circuit
  v
dp_dq, Hop
  |
  v
NetlistBoundaryInterface solves unknown characteristic
  |
  |  du = [dP, dQ]
  v
P^{n+1}, Q^{n+1}
  |
NetlistBoundaryManager records final interface state
  |
  |  real mode: queue final P/Q by surfaceId
  v
class1DflowSolver finishes all numerical objects for timestep n
  |
  |  finalizeNetlistTimestep(n)
  v
NetlistBoundaryManager pushes all queued final P/Q values
  |
  |  adapter.update_state(...) for every pending surface
  |  adapter.finalize_timestep(n) once
  v
CRIMSON advances/finalizes the global netlist state once for timestep n
```

The important separation is:

```text
STARFiSh XML:
  maps the 1D boundary to a netlist surface.

CRIMSON netlist XML:
  defines the actual circuit.

Python interface:
  translates between 1D characteristic variables and CRIMSON's P/Q law.
```

The end-of-timestep split is intentional. Each 1D boundary solves its own
characteristic problem and records the final interface state, but no boundary
condition object should independently advance the global netlist. The flow
solver is the only place that knows all boundary objects have run for timestep
`n`, so it calls:

```python
FlowSolver.finalizeNetlistTimestep(n)
```

That call flushes every pending surface update to the one shared adapter and
then finalizes CRIMSON once. This mirrors the CRIMSON pattern:

```text
compute interface law during the flow solve
collect final interface flow/pressure
update/finalize the netlist once at the end of the timestep
```

## Milestone 1: XML Visibility

Goal: prove the solver can read a `Netlist` boundary condition from `input.xml`.

Implementation steps:

1. Add `Netlist` and `_Netlist` to `UtilityLib/networkXml043.py`.
2. Register XML fields:

   ```python
   ["surfaceId", "flowSign", "Rtilde", "S"]
   ```

   `flowSign`, `Rtilde`, and `S` are optional for `_Netlist`.
   In the real coupled mode, omit `Rtilde` and `S`; the CRIMSON netlist wrapper
   provides them as `(dp_dq, Hop)`.

3. Add a skeletal Type 2 class in `NetworkLib/classBoundaryConditions.py`:

   ```python
   class Netlist(BoundaryConditionType2):
       def __init__(self):
           self.type = 2
           self.surfaceId = None
           self.networkDirectory = None
           self.flowSign = 1.0
           self.Rtilde = None
           self.S = 0.0
   ```

4. Load a case and verify that the object is created with the expected parsed
   values. This milestone does not need to solve the boundary yet.

## Milestone 2: Single-Tube Robin Behavior

Goal: make `_Netlist` behave like `_Resistance` for one outlet.

Use the existing baseline case:

```text
examples/baseline_resistance/input.xml
```

Duplicate it, then replace:

```xml
<_Resistance>
  <Rc unit="Pa s m-3">133320000.0</Rc>
</_Resistance>
```

with:

```xml
<_Netlist>
  <surfaceId>0</surfaceId>
  <Rtilde unit="Pa s m-3">133320000.0</Rtilde>
  <S unit="Pa">0.0</S>
</_Netlist>
```

Expected result:

```text
P_out and Q_out match the _Resistance case.
```

This validates the 1D characteristic coupling before adding any C++ netlist
code.

## Boundary Math

At a 1D boundary, one characteristic comes from the vessel interior and the
other characteristic is unknown. The Type 2 boundary condition must solve:

```text
1D characteristic compatibility
P = Rtilde * Q + S
```

The characteristic transform gives:

```text
[dP, dQ]^T = R_char * [omega_known, omega_unknown]^T
```

Since `P = P_old + dP` and `Q = Q_old + dQ`, the unknown characteristic can be
solved directly for the affine netlist law. No Newton solve is needed for this
first Robin-style interface.

Newton or finite-difference Jacobians are only needed if the 0D side exposes a
nonlinear residual directly:

```text
F(P, Q, state) = 0
```

instead of exposing:

```text
P = Rtilde * Q + S
```

## Milestone 3: Python Manager Layer

Even for a single tube, add a manager abstraction before calling C++ directly.

Recommended file split:

```text
NetworkLib/classBoundaryConditions.py
  Netlist
    Thin STARFiSh Type 2 caller.

NetworkLib/netlistInterface.py
  NetlistBoundaryInterface
    Owns the 1D characteristic solve and the Robin law.

NetworkLib/netlistManager.py
  NetlistBoundaryManager
    Owns surface registration, fake-vs-C++ adapter selection,
    coefficient calls, and timestep finalization.

ext / compiled binding
  Owns the actual C++ CRIMSON netlist wrapper.
```

The `Netlist` class in `classBoundaryConditions.py` should remain small:

```python
class Netlist(BoundaryConditionType2):
    def __call__(self, omega_known, du_prescribed, R, L, nmem, n, dt, P, Q, A, Z1, Z2):
        return self.interface.solve(
            omega_known=omega_known,
            R=R,
            nmem=nmem,
            n=n,
            dt=dt,
            P=P,
            Q=Q,
            A=A,
            Z1=Z1,
            Z2=Z2,
        )
```

The interface layer owns the characteristic algebra:

```python
class NetlistBoundaryInterface:
    def solve(self, omega_known, R, nmem, n, dt, P, Q, A, Z1, Z2):
        time = (n + 1) * dt
        if not self.manager.flow_permitted(self.surface_id, n, time, dt):
            omega_vector = solve_prescribed_flow_characteristic(
                self.position,
                omega_known,
                R,
                Q,
                prescribed_flow=0.0,
            )
        else:
            Rtilde, S = self.manager.compute_coefficients(
                surface_id=self.surface_id,
                timestep=n,
                time=time,
                dt=dt,
                pressure=P,
                flow=self.flow_sign * Q,
            )

            omega_vector = self.solve_unknown_characteristic(
                position=self.position,
                omega_known=omega_known,
                R=R,
                P=P,
                Q=Q,
                Rtilde=Rtilde,
                S=S,
            )

        du = np.dot(R, omega_vector)
        P_new = P + du[0]
        Q_new = Q + du[1]
        self.manager.record_boundary_state(
            self.surface_id,
            n,
            time,
            dt,
            P_new,
            self.flow_sign * Q_new,
        )
        return du, self.compute_dq_in_out(omega_vector, R)
```

Manager-level conceptual API:

```python
class NetlistBoundaryManager:
    def set_netlist_file(self, netlist_file):
        ...

    def register_boundary(self, surface_id, vessel_id, position):
        ...

    def set_output_directory(self, output_directory):
        ...

    def start_timestep(self, timestep, time, dt):
        ...

    def compute_coefficients(self, surface_id, timestep, time, dt, pressure, flow):
        return Rtilde, S

    def compute_update_coefficients(self, surface_id, timestep, time, dt, flow):
        return Rtilde, S

    def flow_permitted(self, surface_id, timestep, time, dt):
        return True

    def record_boundary_state(self, surface_id, timestep, time, dt, pressure, flow):
        ...

    def finalize_timestep(self, timestep):
        ...
```

For the first version, the manager can return constants from XML:

```text
Rtilde, S
```

Later, the same manager calls the CRIMSON C++ wrapper.

The reason to add this layer early is that real netlists can couple multiple
surfaces. Each boundary condition should not independently own or finalize a
separate netlist.

## Current Python-Side Roles

The current code is intentionally split into four small roles.

```text
NetworkLib/classBoundaryConditions.py
```

This is the STARFiSh entry point. `Netlist` is a Type 2 boundary condition, but
it should stay thin. Its job is to receive parsed XML values, identify the
vessel end (`position`), register the boundary once, and call the interface
solver every time STARFiSh evaluates that boundary.

```text
NetworkLib/netlistInterface.py
```

This owns the numerical 1D/0D interface math. It asks for `(dp_dq, Hop)`, solves
the unknown characteristic, returns `du = [dP, dQ]`, and records the final
interface state. This is where any future nonlinear characteristic solve should
live if the CRIMSON side exposes a residual instead of an affine law.

```text
NetworkLib/netlistManager.py
```

This owns case-level netlist state. There is one global netlist file,
`netlist_surfaces.xml`, and many possible STARFiSh boundaries mapped by
`surfaceId`. The manager registers those mappings, chooses fake constant mode
versus real CRIMSON mode, queues final boundary states, and finalizes the
adapter once per timestep.

The manager is deliberately different from the adapter:

```text
manager = STARFiSh coupling coordinator
adapter = thin Python wrapper over compiled C++
```

```text
UtilityLib/crimsonNetlistAdapter.py
```

This file should contain no 1D solver logic. It imports the compiled
`crimson_starfish_bridge` module, loads the fixed CRIMSON XML file, asks C++ for
coefficients, pushes final pressure/flow values, and calls finalization. It is
the only Python file that should know about the compiled binding details.

```text
SolverLib/class1DflowSolver.py
```

This owns timestep-level initialization and finalization. Before boundaries are evaluated, it calls:

```python
get_default_netlist_manager().start_timestep(n, (n + 1) * self.dt, self.dt)
```

After every numerical object has run for a timestep, it calls:

```python
get_default_netlist_manager().finalize_timestep(n)
```

That is the point where pending surface states become CRIMSON netlist state.

## Milestone 4: Single-Surface C++ Bridge

Once `_Netlist` matches `_Resistance`, replace the fake manager coefficients
with a C++ bridge.

Minimum bridge API:

```python
load()
compute_implicit_coefficients(surface_id, timestep, time, dt, q_current)
update_state(surface_id, timestep, time, dt, p_final, q_final)
finalize_timestep(timestep)
```

Minimum returned data:

```text
Rtilde, S
```

The STARFiSh boundary condition should not care whether these values came from
XML constants, a fake Python object, or the CRIMSON netlist solver.

In real mode, the CRIMSON netlist XML file is fixed to:

```text
netlist_surfaces.xml
```

in the same directory as STARFiSh `input.xml`.

STARFiSh should not parse the circuit topology, components, prescribed nodal
pressures, component flows, diode states, or capacitor histories. That logic
belongs inside CRIMSON's netlist code.

Current C++ bridge status:

```text
ext/StarfishBridge.cpp
```

is the active build target for STARFiSh. It is intentionally kept in the
STARFiSh `ext/` tree so this project can be built and tested without modifying
CRIMSON's SCons build chain. The current bridge stores one `SurfaceState` per
STARFiSh `surfaceId` and uses one direct CRIMSON `NetlistCircuit` per surface:

```text
current:
  one global netlist_surfaces.xml
  many registered surface states
  surfaceId -> direct NetlistCircuit mapping
  coefficient lookup per surface
  delayed global finalization after all surfaces update
```

The important remaining caveat is that `surfaceId` is used as the STARFiSh-side
surface key and CRIMSON output surface index, while the CRIMSON XML circuit is
selected by construction order. The manager passes sorted registered surface IDs
at load time so the mapping is deterministic. We still need explicit validation
against real CRIMSON `indicesOfNetlistSurfaces` cases.

## CRIMSON Netlist File Ownership

The relevant CRIMSON source directory is:

```text
/home/sadid/crimson/cfs_reg/CRIMSONFlowsolver/flowsolver/src/
```

The STARFiSh side now follows the CRIMSON convention directly. The input file
is always named:

```text
netlist_surfaces.xml
```

and it must be placed next to STARFiSh `input.xml` in the case directory.
STARFiSh should not accept per-boundary netlist filenames in `input.xml`; that
keeps case layout predictable and avoids path ambiguity.

The STARFiSh `input.xml` should only contain:

```text
surfaceId
flowSign
```

The CRIMSON netlist file contains the actual circuit.

## CRIMSON Files to Wrap

Core netlist solver files:

```text
NetlistCircuit.hxx
NetlistCircuit.cxx
CircuitData.hxx
CircuitData.cxx
CircuitComponent.hxx
CircuitComponent.cxx
CircuitPressureNode.hxx
CircuitPressureNode.cxx
NetlistXmlReader.hxx
NetlistXmlReader.cxx
datatypesInCpp.hxx
fileReaders.hxx
fileReaders.cxx
fileWriters.hxx
fileWriters.cxx
indexShifters.hxx
customCRIMSONContainers.hxx
debuggingToolsForCpp.hxx
```

CRIMSON boundary-condition wrapper layer:

```text
NetlistBoundaryCondition.hxx
NetlistBoundaryCondition.cxx
AbstractBoundaryCondition.hxx
AbstractBoundaryCondition.cxx
BoundaryConditionFactory.hxx
BoundaryConditionFactory.cxx
BoundaryConditionManager.hxx
BoundaryConditionManager.cxx
FortranBoundaryDataPointerManager.hxx
FortranBoundaryDataPointerManager.cxx
```

Optional advanced modes:

```text
NetlistBoundaryCircuitWhenDownstreamCircuitsExist.hxx
NetlistBoundaryCircuitWhenDownstreamCircuitsExist.cxx
NetlistClosedLoopDownstreamCircuit.hxx
NetlistClosedLoopDownstreamCircuit.cxx
ClosedLoopBoundaryConditionSubsection.hxx
ClosedLoopBoundaryConditionSubsection.cxx
Netlist3DDomainReplacement.hxx
Netlist3DDomainReplacement.cxx
NetlistZeroDDomainCircuit.hxx
NetlistZeroDDomainCircuit.cxx
```

The ideal long-term path is to use the CRIMSON boundary-condition wrapper layer
through `NetlistBoundaryCondition` or `BoundaryConditionFactory`, because that
is closest to how CRIMSON already computes `(dp_dq, Hop)` for the higher
dimensional solver.

Current practical path:

```text
ext/StarfishBridge.cpp -> NetlistCircuit directly
```

We tried the wrapper-layer route first, but importing the rebuilt Python 3
extension failed with an unresolved `PyString_FromString` symbol. That symbol
comes from older CRIMSON Python-control-system code pulled in by the fuller
boundary-condition wrapper path. Until that is isolated or ported cleanly, the
active bridge uses `NetlistCircuit` directly while preserving the same Python
API and timestep flow.

## C++ Calling Shape

Minimal direct `NetlistCircuit` sequence:

```cpp
NetlistCircuit circuit(
    hstep,
    surfaceIndex,
    netlistIndex,
    restarted,
    alfi,
    delt,
    startingTimestepIndex);

circuit.setPointersToBoundaryPressuresAndFlows(&pressure, &flow, 1);
circuit.createCircuitDescription();
circuit.closeAllDiodes();
circuit.detectWhetherClosedDiodesStopAllFlowAt3DInterface();
circuit.initialiseCircuit();

circuit.initialiseAtStartOfTimestep();
auto coeffs = circuit.computeImplicitCoefficients(
    timestepNumber,
    timeAtNplus1,
    alfi_delt);
circuit.updateLPN(timestepNumber);
circuit.finalizeLPNAtEndOfTimestep();
```

Preferred boundary-condition wrapper sequence:

```cpp
NetlistBoundaryCondition bc(
    surfaceIndex,
    hstep,
    delt,
    alfi,
    startingTimestepIndex,
    maxsurf,
    nstep,
    downstreamSubcircuits);

bc.setPressureAndFlowPointers(&pressure, &flow);
bc.initialiseModel();

bc.initialiseAtStartOfTimestep();
bc.computeImplicitCoeff_solve(timestepNumber);
double Rtilde = bc.getdp_dq();
double S = bc.getHop();
bc.updateLPN(timestepNumber);
bc.finaliseAtEndOfTimestep();
```

The Python adapter hides the C++ sequence behind a small API:

```python
class CrimsonNetlistAdapter:
    def load(self, dt=None):
        ...

    def compute_implicit_coefficients(self, surface_id, timestep, time, dt, flow):
        return dp_dq, hop

    def update_state(self, surface_id, timestep, time, dt, pressure, flow):
        ...

    def finalize_timestep(self, timestep):
        ...
```

## Existing C++ Starting Point

Current prototype files:

```text
/home/sadid/crimson/cfs_reg/CRIMSONFlowsolver/flowsolver/src/Netlist1DWrapper.hxx
/home/sadid/crimson/cfs_reg/CRIMSONFlowsolver/flowsolver/src/Netlist1DWrapper.cxx
```

These files are useful design references, but they do not have to become the
active wrapper. For this project, the cleaner build path is:

```text
STARFiSh owns:
  ext/StarfishBridge.cpp
  ext/bindings.cpp
  ext/CMakeLists.txt

CRIMSON source provides:
  netlist classes included/linked by the STARFiSh extension
```

This avoids adding experimental 1D code to CRIMSON's main source tree and avoids
threading a prototype through CRIMSON's SCons build. If `Netlist1DWrapper` has a
better internal call sequence, copy the idea into `ext/StarfishBridge.cpp`
rather than making STARFiSh depend on that file directly.

Current wrapper shape:

```cpp
std::pair<double, double> computeImplicitCoefficients(
    int surfaceIndex,
    int timestep,
    double time,
    double dt,
    double flow);

void updateState(
    int surfaceIndex,
    int timestep,
    double time,
    double dt,
    double pressure,
    double flow);
```

This is aligned with the 1D coupling plan because it already returns:

```text
(Rtilde, S) == (dp_dq, Hop)
```

The useful ideas to borrow are:

- Store one `SurfaceState` per CRIMSON surface.
- Give each state its own pressure and flow scalar whose addresses are passed to
  `NetlistBoundaryCondition`.
- Use `BoundaryConditionFactory` / `NetlistBoundaryCondition`, because that is
  closest to the real CRIMSON 3D path.
- Begin a timestep once, compute coefficients as needed, then finalize once.

Important limitations to address before multi-surface use:

- `updateState()` finalizes the timestep immediately. For multiple surfaces,
  all final `P/Q` values must be pushed first, then the netlist should finalize
  once.
- `ensureDtMatches_()` requires `dt == config_.delt`. STARFiSh may adapt `dt`
  depending on CFL, so either the wrapper must support timestep-specific `dt`
  or the 1D solver must run with a fixed compatible timestep.
- The wrapper currently exposes scalar `(dp_dq, Hop)` per surface. That is fine
  for the first diagonal coupling. A later multi-surface version may need:

  ```text
  P_i = sum_j M_ij Q_j + S_i
  ```

- Sign convention must be verified. We need a clear rule for whether positive
  STARFiSh `Q` means flow leaving the 1D domain or entering the netlist.
- Netlist file discovery is deliberately fixed. The STARFiSh case directory
  must provide `netlist_surfaces.xml` next to `input.xml`.

Recommended bridge shape for the next implementation:

```cpp
class StarfishBridge {
public:
    void load(const std::string& netlist_xml_path,
              const std::vector<int>& surface_ids);

    std::pair<double, double> compute_implicit_coefficients(
        int surface_id,
        int timestep,
        double time,
        double dt,
        double flow);

    void update_state(
        int surface_id,
        int timestep,
        double time,
        double dt,
        double pressure,
        double flow);

    void finalize_timestep(int timestep);

private:
    struct SurfaceState {
        double pressure;
        double flow;
        boost::shared_ptr<NetlistBoundaryCondition> bc;
    };

    std::map<int, SurfaceState> surfaces_;
};
```

The Python API can remain stable while the C++ implementation changes.

## Milestone 5: Multi-Surface Coupling

After the single-tube case works:

1. Map each STARFiSh boundary to a CRIMSON `surfaceId`.
2. Validate surface ordering and sign conventions.
3. Compute coefficients for all surfaces together.
4. Solve each 1D boundary using the current diagonal law:

   ```text
   P_i = Rtilde_i * Q_i + S_i
   ```

5. Update all final interface `P/Q` values.
6. Finalize the netlist once per timestep.

The first multi-surface implementation can remain diagonal. The manager should
still be designed so a full matrix form can be added later:

```text
P = M Q + S
```

## First Definition of Done

The first complete milestone is:

```text
1. XML accepts _Netlist.
2. _Netlist is instantiated as a Type 2 boundary condition.
3. Single-tube _Netlist case runs.
4. With Rtilde=Rc and S=0, _Netlist reproduces _Resistance.
```

Only after this should the C++ netlist wrapper become part of the run path.

## Current Implementation Notes: Timestep, Lifecycle, and Outputs

This section records the current state of the implementation after the first
single-surface and multi-surface bridge work. It should be treated as the
developer-facing reference for how the Python solver, Python coupling layer, and
CRIMSON C++ netlist bridge currently communicate.

### STARFiSh Timestep Policy

STARFiSh currently uses one fixed solver timestep per simulation run. It does
not recompute `dt` dynamically during the time loop.

The timestep is selected once in `FlowSolver.initializeTimeVariables()`:

```python
dt = CFL * dz / c
self.dt = min(dt_min)
self.nTSteps = int(np.ceil(self.totalTime / self.dt))
```

The solve loop then advances with:

```python
for n in range(self.nTSteps):
    ...
```

Therefore the current netlist coupling assumes:

```text
dt is fixed after solver initialization
nTSteps is fixed after solver initialization
all boundary objects receive the same dt for the full run
```

`automaticGridAdaptation` is separate from timestep adaptation. The solver has
logic to evaluate and propose CFL-consistent grid corrections, but it does not
perform runtime CFL-based `dt` adaptation. `minSaveDt` is also not a solver
timestep control; it only controls the output save stride:

```text
nSaveSkip = ceil(minSaveDt / dt)
saveDt    = nSaveSkip * dt
```

This fixed-`dt` behavior is important for CRIMSON netlist coupling because the
CRIMSON netlist code was written around a fixed `delt` value.

### Alpha and `alfi_delt`

CRIMSON's netlist code receives two time-integration values:

```text
delt      = dt
alfi      = generalized-alpha alpha_f weight
alfi_delt = alfi * delt
```

The netlist uses `alfi_delt` when forming algebraic equations for dynamic
components such as capacitors and inductors. For example, capacitor terms are
scaled by the time discretization, so the value passed into
`computeImplicitCoefficients()` directly affects `(dp_dq, Hop)`.

STARFiSh is not a generalized-alpha solver. The active 1D solver path is an
explicit MacCormack-style predictor/corrector method. For the current bridge we
therefore use:

```text
alfi = 1.0
alfi_delt = dt
```

This is closest to a backward-Euler-style interpretation on the netlist side and
keeps the C++ bridge simple while STARFiSh owns the 1D explicit update.

Current C++ bridge behavior:

```cpp
StarfishBridge(int hstep, double alfi, double delt)

compute_implicit_coefficients(...):
    alfi_delt = alfi * delt
    NetlistCircuit::computeImplicitCoefficients(timestep, time, alfi_delt)

compute_update_coefficients(...):
    NetlistCircuit::computeImplicitCoefficients(timestep, time, delt)
```

The bridge currently enforces fixed `dt`:

```text
runtime dt must match the bridge construction delt
```

If STARFiSh later adds true adaptive timestep support, the netlist bridge will
need either a safe way to rebuild/update CRIMSON's netlist timestep state or a
clear policy that netlist-coupled runs must use fixed `dt`.

### Current Per-Timestep Flowchart

The current implementation mirrors CRIMSON's lifecycle as closely as possible
without embedding CRIMSON's Fortran driver. STARFiSh owns the 1D solve order;
the Python manager coordinates the global netlist state; the C++ bridge owns
CRIMSON's `NetlistCircuit` objects.

For every global timestep `n`:

```text
FlowSolver.MacCormack_Field()
  |
  |  fixed dt from FlowSolver.dt
  v
FlowSolver.startNetlistTimestep(n)
  |
  v
NetworkLib.netlistManager.NetlistBoundaryManager.start_timestep(...)
  |
  v
UtilityLib.crimsonNetlistAdapter.CrimsonNetlistAdapter.start_timestep(...)
  |
  v
ext.StarfishBridge.start_timestep(...)
  |
  v
for each registered C++ SurfaceState:
  NetlistCircuit.initialiseAtStartOfTimestep()
```

Then STARFiSh loops through the numerical objects in tree order:

```text
for numericalObject in FlowSolver.numericalObjects:
  numericalObject()
```

When a `_Netlist` boundary object is reached:

```text
classBoundaryConditions.Netlist
  |
  |  current P, Q, known omega, characteristic matrix R, n, dt
  v
NetworkLib.netlistInterface.NetlistBoundaryInterface.solve(...)
  |
  |  request affine pressure-flow law
  v
NetlistBoundaryManager.compute_coefficients(surfaceId, timestep, time, dt, P, Q)
  |
  v
CrimsonNetlistAdapter.compute_implicit_coefficients(...)
  |
  v
StarfishBridge.compute_implicit_coefficients(...)
  |
  v
NetlistCircuit.computeImplicitCoefficients(...)
  |
  |  returns dp_dq, Hop
  v
NetlistBoundaryInterface solves unknown characteristic omega
  |
  |  P_new = dp_dq * Q_new + Hop
  |  [dP, dQ]^T = R_char * [omega_known, omega_unknown]^T
  v
P^{n+1}, Q^{n+1}
  |
  v
NetlistBoundaryManager.record_boundary_state(surfaceId, P_new, Q_new)
```

After every numerical object for the timestep has run:

```text
FlowSolver.finalizeNetlistTimestep(n)
  |
  v
NetlistBoundaryManager.finalize_timestep(n)
  |
  |  for every pending real-netlist surface:
  |    compute_update_coefficients(...)
  |    adapter.update_state(surfaceId, P_final, Q_final)
  |
  v
StarfishBridge.update_state(...)
  |
  v
NetlistCircuit.updateLPN(timestep)
  |
  |  once all pending surfaces have been pushed:
  v
StarfishBridge.finalize_timestep(n)
  |
  v
for each registered C++ SurfaceState:
  NetlistCircuit.finalizeLPNAtEndOfTimestep()
  NetlistCircuit.writePressuresFlowsAndVolumes(...)
```

This separation is deliberate:

```text
boundary solve:
  compute final 1D interface P/Q for one surface

manager finalization:
  push all final interface P/Q values
  advance/finalize the global netlist once
```

No individual boundary object should independently finalize the global CRIMSON
netlist, because a case can contain multiple netlist surfaces.

### Vessel and Surface Handling

STARFiSh handles vessels in the normal tree traversal order. Each root boundary,
field object, connection, distal boundary, communicator, and runtime memory
object appears in `FlowSolver.numericalObjects`. Netlist coupling only changes
what happens when one of those boundary objects is a `_Netlist`.

For each `_Netlist` boundary:

```text
vesselId  -> STARFiSh vessel that owns this boundary
position  -> start or end of the 1D vessel
surfaceId -> STARFiSh-facing netlist surface label
flowSign  -> sign conversion between STARFiSh Q and CRIMSON interface flow
```

The CRIMSON circuit file remains global:

```text
netlist_surfaces.xml
```

It must live next to STARFiSh `input.xml` in the case directory. STARFiSh does
not parse the circuit topology. It only maps each 1D boundary to a surface id.

The manager registers all real netlist-backed surfaces and passes the sorted
surface ids to the C++ bridge. The bridge maps that sorted order to CRIMSON
netlist circuit indices:

```text
sorted STARFiSh surfaceId -> CRIMSON netlist circuit index

surfaceId 0 -> netlistIndex 0
surfaceId 1 -> netlistIndex 1
surfaceId 5 -> netlistIndex 2
```

Each C++ `SurfaceState` owns:

```text
pressure scalar
flow scalar
next_timestep_write_start
NetlistCircuit
```

The pressure and flow scalar addresses are passed into CRIMSON so
`NetlistCircuit` can read the current interface state in the same style as the
original CRIMSON pointer-based coupling.

Current multi-surface behavior is diagonal:

```text
P_i = dp_dq_i * Q_i + Hop_i
```

The first implementation does not assemble or expose a full cross-surface
matrix:

```text
P_i = sum_j M_ij Q_j + S_i
```

That is a later extension if coupled netlists require off-diagonal interface
terms.

### Current File Responsibilities

The current implementation has the following active flow:

```text
NetworkLib/classBoundaryConditions.py
  Netlist Type 2 boundary condition.
  Thin STARFiSh caller that receives XML values, sets position, and delegates
  the characteristic solve.

NetworkLib/netlistInterface.py
  Mathematical 1D/netlist interface.
  Solves the unknown characteristic from the affine CRIMSON law:
      P = dp_dq * Q + Hop

NetworkLib/netlistManager.py
  Case-level netlist coordinator.
  Registers surfaces, owns the global netlist file path, starts timesteps,
  computes coefficients, records final P/Q states, and finalizes once.

UtilityLib/crimsonNetlistAdapter.py
  Thin Python wrapper over the compiled nanobind module.
  No 1D math should live here.

ext/StarfishBridge.cpp
  C++ bridge that owns CRIMSON NetlistCircuit instances.
  Handles surface registration, start/update/finalize lifecycle calls, and
  pressure/flow/volume output writing.

ext/bindings.cpp
  Nanobind exposure of StarfishBridge as crimson_starfish_bridge.CrimsonBridge.

solver.py
  External case runner.
  Creates results/SolutionData_<number> and tells the netlist manager to write
  CRIMSON netlist history files there.
```

## CRIMSON Python Controller Ownership

Python-based parameter controllers belong to CRIMSON's netlist subsystem, not
to the STARFiSh 1D solver or the 1D characteristic interface.

The existing CRIMSON 3D architecture is:

```text
CRIMSON Fortran 3D solver
  |
  v
BoundaryConditionManager
  |
  +-- NetlistCircuit
  |
  +-- ControlSystemsManager
        |
        +-- native C++ controllers
        |
        +-- embedded Python 2 controller scripts
```

`NetlistCircuit` owns the circuit equations and state, but it does not by
itself create and execute all parameter controllers. In the 3D solver, the
surrounding `BoundaryConditionManager` and `ControlSystemsManager` provide that
functionality.

### CRIMSON 3D Initialization

The normal CRIMSON setup performs the following work:

```text
1. Initialize the embedded Python interpreter.
2. Read netlist_surfaces.xml.
3. Construct the NetlistCircuit objects.
4. Read component and node controller declarations.
5. BoundaryConditionManager creates one ControlSystemsManager.
6. ControlSystemsManager creates the requested controllers.
7. Each controller receives a pointer to the netlist parameter it controls.
```

Examples of controlled quantities include:

```text
component resistance
component compliance
component unstressed volume
prescribed component flow
prescribed nodal pressure
heart elastance parameters
```

A Python controller receives the current controlled parameter, fixed `delt`,
and dictionaries containing the current netlist pressures, flows, and volumes.
The value returned by Python is written directly into the corresponding C++
netlist parameter.

Controller priorities and controller-to-controller broadcast dictionaries are
also managed entirely by CRIMSON's `ControlSystemsManager`.

### CRIMSON 3D Timestep Lifecycle

The simplified CRIMSON sequence is:

```text
for every timestep n:

  NetlistCircuit::initialiseAtStartOfTimestep()

  for every required 3D flow solve:
      compute dp_dq and Hop
      3D solver applies:
          P = dp_dq * Q + Hop

  receive final converged interface flow/pressure

  NetlistCircuit::updateLPN(n)
  NetlistCircuit::finalizeLPNAtEndOfTimestep()

  write netlist pressure/flow/volume histories

  ControlSystemsManager::updateBoundaryConditionControlSystems()
      -> run Python and native controllers
      -> modify netlist parameters for timestep n+1
```

Therefore, controllers do not return `dp_dq` or `Hop` directly. They modify
resistances, compliances, prescribed values, elastances, or other circuit
parameters. The next netlist matrix construction then produces coefficients
that include those updated values.

### STARFiSh Responsibility

STARFiSh should continue treating CRIMSON as a black-box boundary-condition
solver. The intended communication remains:

```text
STARFiSh -> CRIMSON:
  surfaceId
  timestep
  time
  fixed dt
  interface pressure
  interface flow

CRIMSON -> STARFiSh:
  dp_dq
  Hop
  interface flow-permission / diode state
```

STARFiSh should not implement:

```text
controller script loading
controller priorities
controller broadcast dictionaries
controller restart/pickling
component parameter modification
heart-controller equations
```

Those remain CRIMSON responsibilities behind the interface.

The 1D-specific code only uses the returned affine law:

```text
P_interface = dp_dq * Q_interface + Hop
```

to solve the unknown characteristic and obtain the final 1D boundary pressure
and flow.

### Current Limitation

The current STARFiSh bridge constructs `NetlistCircuit` directly:

```text
STARFiSh Python 3.11
  -> CrimsonNetlistAdapter
  -> nanobind module
  -> StarfishBridge
  -> NetlistCircuit
```

This path supports passive circuits and CRIMSON's normal netlist solve, but it
bypasses the 3D-level controller ownership provided by:

```text
BoundaryConditionManager
ControlSystemsManager
embedded CRIMSON Python runtime
```

Consequently, adding controller declarations to `netlist_surfaces.xml` is not
enough by itself. The direct `NetlistCircuit` bridge does not currently create
or update those controllers.

### Python Runtime Constraint

STARFiSh runs in Python 3.11, while the existing CRIMSON controller layer uses
the Python 2 C API, including calls such as:

```text
PyString_*
PyInt_*
```

Loading that Python 2 controller runtime into the same process as STARFiSh's
Python 3 interpreter is unsafe and can produce missing-symbol or interpreter
ABI failures.

This is a runtime separation issue, not a reason to reimplement CRIMSON
controllers in STARFiSh.

### Proposed Full-Controller Architecture

For full CRIMSON controller compatibility, the clean target is:

```text
STARFiSh Python 3.11
  |
  | P, Q, timestep, time, dt
  | dp_dq, Hop, interface mode
  v
CRIMSON netlist runtime process
  |
  +-- NetlistCircuit
  +-- ControlSystemsManager
  +-- embedded Python 2.7
```

The separate process is only a Python-runtime boundary. It must not duplicate
the controller implementation. CRIMSON still owns:

```text
netlist parsing
circuit state
controller creation
Python controller execution
parameter updates
diode switching
history and restart state
```

STARFiSh only communicates the numerical interface data already required by
the coupling.

Every netlist should use the same CRIMSON runtime path. Passive circuits simply
create zero Python controllers. Controller support should not be presented as
a user-selectable coupling mode.

### Recommended Implementation Order

Before changing the current runtime, proceed in small verified stages:

```text
1. Preserve the existing passive-netlist baseline results.

2. Build a standalone CRIMSON-owned runtime using the known Python 2.7
   environment.

3. Make that runtime load and solve the existing passive resistor case.

4. Verify that its dp_dq, Hop, pressure, flow, and volume histories match the
   current in-process bridge.

5. Add CRIMSON ControlSystemsManager creation using controller declarations
   already present in netlist_surfaces.xml.

6. Run one minimal controlled-resistance test and verify that the parameter
   changes affect the next timestep's coefficients.

7. Only after equivalence is demonstrated, route normal STARFiSh netlist runs
   through the CRIMSON-owned runtime.
```

The build should use the designated CRIMSON Python environment, expected at:

```text
/home/sadid/miniconda3/envs/flow/bin/python
/home/sadid/miniconda3/envs/flow/include/python2.7/
/home/sadid/miniconda3/envs/flow/lib/
```

The STARFiSh source tree should not modify CRIMSON source files. Any small
runtime adapter required for initialization should live in `ext/`, while the
actual netlist and controller classes continue to come from the CRIMSON
libraries.

## Closed-Loop Netlist Support Plan

Closed-loop netlists are a separate extension beyond independent boundary
circuits and normal multi-surface output handling.

CRIMSON distinguishes:

```text
boundary netlist circuits
  One circuit attached to each 1D/3D interface.

closed-loop downstream circuits
  Shared circuits that connect multiple boundary netlists and close the
  cardiovascular loop.
```

The current STARFiSh bridge constructs independent `NetlistCircuit` objects.
That representation is sufficient for uncoupled outlet or inlet circuits, but
it does not reproduce CRIMSON's shared downstream closed-loop connectivity.

### Relevant CRIMSON Classes

The closed-loop implementation is primarily owned by:

```text
NetlistBoundaryCircuitWhenDownstreamCircuitsExist.hxx/.cxx
NetlistClosedLoopDownstreamCircuit.hxx/.cxx
ClosedLoopDownstreamSubsection.hxx/.cxx
ClosedLoopBoundaryConditionSubsection.hxx/.cxx
```

The relevant construction, controller-registration, update, and finalization
loops also appear in:

```text
BoundaryConditionManager.hxx/.cxx
multidom.cxx
itrdrv.f90
```

These classes should be reused. STARFiSh should not create a second
implementation of closed-loop circuit connectivity.

### Closed-Loop Input Files

A closed-loop case can require both:

```text
netlist_surfaces.xml
netlist_closed_loop_downstream.xml
```

`NetlistXmlReader` owns the boundary circuit description.
`NetlistDownstreamXmlReader` owns the downstream closed-loop description.

Both files should eventually live in the STARFiSh case directory beside:

```text
input.xml
```

STARFiSh should still avoid parsing component topology itself. The CRIMSON
runtime should load both files and construct the complete circuit system.

### Required System Ownership

Closed-loop support requires a system-level owner:

```text
CRIMSON closed-loop netlist runtime
  |
  +-- boundary netlist circuits
  +-- downstream closed-loop circuits
  +-- boundary subsections
  +-- downstream subsections
  +-- shared node/flow connections
  +-- ControlSystemsManager
```

This differs from the current direct mapping:

```text
surfaceId -> independent NetlistCircuit
```

The shared downstream circuit must be created and advanced once globally. It
must not be independently owned or finalized by each STARFiSh boundary object.

### Initialization Order

The expected CRIMSON-compatible setup order is:

```text
1. Initialize PETSc/MPI and the CRIMSON Python runtime.

2. Load netlist_surfaces.xml.

3. Load netlist_closed_loop_downstream.xml.

4. Construct every boundary circuit.

5. Construct every downstream closed-loop circuit.

6. Create the boundary and downstream subsection objects.

7. Connect shared pressure nodes and component flows.

8. Initialize the complete connected circuit system.

9. Create component and node controllers for boundary circuits.

10. Create component and node controllers for downstream circuits.
```

Controllers must be created after connectivity is complete because CRIMSON
controllers store direct pointers to circuit parameters, pressures, flows, and
volumes.

### Controller Registration

The current `CrimsonControlSystems` wrapper reproduces the boundary-circuit
loop from:

```cpp
BoundaryConditionManager::createControlSystems()
```

Closed-loop support must add the second CRIMSON loop that reads:

```text
NetlistDownstreamXmlReader component control maps
NetlistDownstreamXmlReader node control maps
```

and calls:

```cpp
ControlSystemsManager::createParameterController(...)
```

for every controlled downstream component and node.

The wrapper should eventually accept separate collections:

```text
boundary circuits
downstream closed-loop circuits
```

Do not generalize the wrapper until the actual CRIMSON downstream circuit
ownership types and construction sequence have been verified.

### Coupling Mathematics

Independent boundary circuits currently expose one diagonal affine law per
surface:

```text
P_i = dp_dq_i * Q_i + Hop_i
```

A shared closed-loop system may mathematically require:

```text
P_i = sum_j M_ij Q_j + S_i
```

where changing flow at one interface can affect pressure at another interface.

Before implementing closed-loop coupling, verify from CRIMSON whether:

```text
1. The shared closed-loop solve is reduced internally to one scalar
   dp_dq_i/Hop_i pair per surface, or

2. The higher-dimensional solver consumes cross-surface terms through a
   coupled matrix/operator.
```

This is the principal mathematical question. The 1D characteristic boundary
solve cannot assume diagonal interface laws until CRIMSON's closed-loop
coefficient path has been traced.

### Timestep Lifecycle

The complete closed-loop system should follow a global lifecycle:

```text
for every timestep n:

  initialize all boundary and downstream circuits

  compute all required interface laws

  solve every STARFiSh boundary characteristic

  collect final P_i/Q_i from all interfaces

  update the connected CRIMSON circuit system once

  finalize all boundary and downstream circuit histories once

  update all Python/native controllers once
```

No individual boundary should independently advance or finalize the downstream
closed-loop state.

### Recommended Closed-Loop Implementation Order

Proceed in separate reviewable stages:

```text
1. Read and document the four CRIMSON closed-loop classes and the corresponding
   BoundaryConditionManager paths.

2. Trace the exact interface coefficient form used by CRIMSON closed-loop
   simulations.

3. Build a standalone check using one existing CRIMSON closed-loop fixture.

4. Verify circuit counts, subsection connections, and controller counts.

5. Advance one timestep entirely inside the standalone CRIMSON check.

6. Compare generated pressure, flow, and volume histories against the original
   CRIMSON fixture.

7. Generalize CrimsonControlSystems to include downstream circuits.

8. Introduce a system-level closed-loop owner behind the STARFiSh interface.

9. Connect STARFiSh only after the standalone CRIMSON lifecycle is equivalent.
```

Closed-loop work should not alter the already verified independent boundary
controller path until these checks pass.

### Netlist Output Files

CRIMSON's netlist writer emits pressure, flow, and volume history files:

```text
netlistFlows_surface_<surfaceId>.dat
netlistPressures_surface_<surfaceId>.dat
netlistVolumes_surface_<surfaceId>.dat
```

The bridge now calls:

```cpp
NetlistCircuit::writePressuresFlowsAndVolumes(next_timestep_write_start)
```

during `StarfishBridge.finalize_timestep(...)`.

Because CRIMSON writes these files using relative paths, `solver.py` passes the
current STARFiSh solution directory into the netlist manager:

```text
results/SolutionData_<number>/
```

The path is forwarded through:

```text
solver.py
  -> NetlistBoundaryManager.set_output_directory(...)
  -> CrimsonNetlistAdapter.set_output_directory(...)
  -> StarfishBridge.set_output_directory(...)
```

During netlist output writing, the bridge temporarily writes from that solution
directory and then restores the previous working directory. This keeps the
CRIMSON netlist outputs beside the STARFiSh HDF5/XML outputs:

```text
results/SolutionData_001/
  vascularNetwork_SolutionData_001.hdf5
  vascularNetwork_SolutionData_001.xml
  netlistFlows_surface_0.dat
  netlistPressures_surface_0.dat
  netlistVolumes_surface_0.dat
  ...
```

For resistor-only circuits, the volume files may contain only the timestep
column because there are no capacitor/volume-tracking components in that branch.

### Current Fixed-Dt Constraint for Streaming and Netlist Runs

For streaming or coupled CRIMSON netlist operation, the current practical rule
is:

```text
choose the STARFiSh grid/CFL so the initialized dt is the dt you want,
then keep that dt fixed for the full run.
```

The current bridge intentionally checks that every runtime `dt` equals the
construction `delt`. This makes mismatches obvious and avoids silently advancing
CRIMSON's netlist histories with inconsistent timestep assumptions.

If a future workflow needs exact user-prescribed `dt`, the clean extension is to
add an explicit STARFiSh input field such as:

```xml
<fixedDt unit="s">...</fixedDt>
```

or:

```xml
<timeStep unit="s">...</timeStep>
```

and make `FlowSolver.initializeTimeVariables()` use that value instead of
deriving `dt` only from CFL. That is a separate feature from runtime adaptive
`dt`.
