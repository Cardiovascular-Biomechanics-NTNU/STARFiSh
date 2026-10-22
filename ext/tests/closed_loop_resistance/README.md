# Exact two-port shared-resistance fixture

This fixture uses arbitrary consistent pressure/flow units. Port resistances
are 2 and 4; both connect to one return junction with resistance 8 leading to
fixed pressure 3. Physical surfaces are 0 and 4, and each interface is node 1.

The exact port response is `p = [[10,8],[8,12]] q + [3,3]`. At prescribed flows
`[1,2]`, pressures are `[29,35]`. The characteristic relations `p1=29-q1` and
`p2=35-2*q2` give the simultaneous solution `q=[1.2,1.6]`, `p=[27.8,31.8]`.

Tests use explicitly defined synthetic inputs, not a physiological waveform.
The carried-input check uses `q=[(n mod 5)-2, 1-(n mod 3)]` with dt=0.001 s.
The valve test makes a private copy, changes the first resistor to a diode,
and alternates first-port candidate flow `+1/-1` and pressure `29/-20` every
two steps; the other candidate flow/pressure are `2/3`. Its active modes select
the actual prescribed quantity. This checks frozen-state probes and repeated
opening/closure against native C++, with no controller or 1D vessel model.

See [the mathematical plan](../../../docs/netlist_closed_loop_implementation_plan.md)
for the coupled equations and [the tests](../../../UnitTesting/test_netlist_closed_loop.py).
