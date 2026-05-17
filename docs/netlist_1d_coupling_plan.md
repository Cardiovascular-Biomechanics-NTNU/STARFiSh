# Netlist 1D Coupling Plan

This note defines the first coupling target between the STARFiSh 1D solver and
the CRIMSON netlist boundary-condition machinery.

The first user-facing boundary condition should be named simply:

```xml
<_Netlist>
  <Rtilde unit="Pa s m-3">133320000.0</Rtilde>
  <S unit="Pa">0.0</S>
  <surfaceId>0</surfaceId>
  <netlistFile>netlist_surfaces.xml</netlistFile>
</_Netlist>
```

Internally, the first version can behave as a Robin pressure-flow condition:

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

## Milestone 1: XML Visibility

Goal: prove the solver can read a `Netlist` boundary condition from `input.xml`.

Implementation steps:

1. Add `Netlist` and `_Netlist` to `UtilityLib/networkXml043.py`.
2. Register XML fields:

   ```python
   ["Rtilde", "S", "surfaceId", "netlistFile"]
   ```

3. Add a skeletal Type 2 class in `NetworkLib/classBoundaryConditions.py`:

   ```python
   class Netlist(BoundaryConditionType2):
       def __init__(self):
           self.type = 2
           self.Rtilde = 1.0
           self.S = 0.0
           self.surfaceId = None
           self.netlistFile = None
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
  <Rtilde unit="Pa s m-3">133320000.0</Rtilde>
  <S unit="Pa">0.0</S>
  <surfaceId>0</surfaceId>
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

Conceptual API:

```python
class NetlistBoundaryManager:
    def load(self, netlist_file):
        ...

    def register_boundary(self, surface_id, vessel_id, position):
        ...

    def compute_coefficients(self, surface_id, timestep, time, dt, pressure, flow):
        return Rtilde, S

    def update_state(self, surface_id, timestep, time, dt, pressure, flow):
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

## Milestone 4: Single-Surface C++ Bridge

Once `_Netlist` matches `_Resistance`, replace the fake manager coefficients
with a C++ bridge.

Minimum bridge API:

```python
load(netlist_file)
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

## Existing C++ Starting Point

Current prototype files:

```text
/home/sadid/crimson/cfs_reg/CRIMSONFlowsolver/flowsolver/src/Netlist1DWrapper.hxx
/home/sadid/crimson/cfs_reg/CRIMSONFlowsolver/flowsolver/src/Netlist1DWrapper.cxx
```

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
- Netlist file discovery should be explicit. The STARFiSh case directory should
  provide `netlist_surfaces.xml` or a path through `<netlistFile>`.

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
