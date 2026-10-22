# Passive Starfish circulation with a shared RC return

This is the first full 1D closed-loop integration fixture. All quantities are SI.
It is a passive startup transient, with no pump or imposed inflow.

- Single uniform vessel: length 0.5 m, 40 nodes, configured duration 0.25 s.
- Proximal endpoint: physical surface 0, external flow = minus axial vessel flow.
- Distal endpoint: physical surface 4, external flow = axial vessel flow.
- Each port has a 1e7 Pa·s/m³ resistor leading to its return junction.
- Return resistor: 1e8 Pa·s/m³ between junctions 1 and 2.
- Return compliance: 2e-9 m³/Pa between junction 1 and reference node 3.
- Vessel initial pressure: 10000 Pa; return initial pressure: 8000 Pa.
- Static parameters, `ConstantPressure` initialization, `MacCormack_Flux`, alpha 1.

The very small nominal runtime memory budget deliberately forces a two-sample
buffer in the current allocator. Validation compares chunked and unchunked
solutions and requires circuit acceptance before network publication.

The physical volume ledger is the spatial integral of vessel area plus
`C*(p_return_1-p_reference_3)`. The reference node is not a bleed. Shared KCL
is an algebraic constraint; the combined total-volume defect also contains
the existing vessel discretization error and is checked under refinement.

The native C++ fixture uses the same normalized surface mapping and physical
inputs; it carries its own circuit state. See
[the integration guide](../../../docs/netlist_py_integration.md) for the native
query initialization profile, limitations and validation commands.

An organized runnable copy and results are kept in
`examples/closed_loop_passive/`. Run the copied case with:

```bash
python3 -B solver.py examples/closed_loop_passive/input.xml -o /tmp/closed-loop-new
python3 -B UnitTesting/validate_closed_loop_backends.py
```
