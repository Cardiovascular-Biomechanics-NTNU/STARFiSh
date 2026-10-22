# Controlled closed-loop lifecycle fixture

SI version of `../closed_loop_passive`, with two synthetic resistance controls.
This is a numerical scheduling fixture, not a calibrated circulation.

The downstream producer (priority 0) reads its previous published pressure,
advances its clock once and broadcasts that pressure. The surface 0 consumer
(priority 1) uses that update's broadcast. Registration encounters upstream
circuits first, so this tests global priority ordering across owners.

Both controllers run before the first solve and every subsequent solve. Repeated
probes reuse prepared targets. The NumPy programs and retained Python 2 native
counterparts implement the same scalar laws. See
`../../../docs/netlist_py_integration.md` for the driver lifecycle and evidence.

As in the passive fixture, the tiny memory allowance forces a two-sample buffer.
