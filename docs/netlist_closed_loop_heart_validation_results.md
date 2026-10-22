# 60-second 1D closed-loop hemorrhage comparison

Both native C++ and reference NumPy simulations completed. The case contains
five actual 1D vessels, a valved LV, two systemic RCR beds, and a shared venous
return. The bleed branch drains externally. It uses the tutorial SI heart and
feedback law and the supplied pure-0D example's return topology and rescaled
parameters. No generated 0D replacement substitutes for the vessel tree.

## Files and reproduction

- [Prepared inputs and model notes](../ext/tests/closed_loop_heart/README.md).
- [Runnable example](../examples/closed_loop_blood_loss_heart/input.xml).
- [Full run report and plots](../examples/closed_loop_blood_loss_heart/results_closed_loop/run_002/heart_report.md).
- [Full accuracy, timing and controller metrics](netlist_closed_loop_heart_validation_results.json).
- [Volume and local circuit diagnostics](../examples/closed_loop_blood_loss_heart/results_closed_loop/run_002/heart_validation.json).

```bash
# Create only when the destination does not already exist:
python3 -B UnitTesting/build_closed_loop_heart.py
# Allocates another results_closed_loop/run_NNN without replacing prior runs:
python3 -B UnitTesting/run_closed_loop_heart.py
python3 -B -m unittest discover -s UnitTesting -p 'test_netlist*.py' -v
```

`run_001` is a one-second pilot; `run_002` is the requested full run. Each backend
has private identical input snapshots, console logs, HDF5 vessel histories,
physical netlist DAT histories, `heart_controller_trace.csv`, and
`heart_monitors.csv`. Full-run and final-five-second figures, an LV pressure-volume
plot and storage-component plots are saved as PNG and PDF. Large example results
follow the repository's existing ignored-output convention; prepared inputs and
this evidence summary are kept under tracked source directories.

## Results

| Measurement | C++ | NumPy |
| --- | ---: | ---: |
| Accepted timesteps | 182,498 | 182,498 |
| Final simulated time, s | 60.0002128501 | 60.0002128501 |
| Solver wall time, s | 1263.378252 | 794.158682 |
| Initial HR, bpm | 69.767442 | 69.767442 |
| Final HR, bpm | 115.771242 | 115.771242 |
| Physical external blood loss, mL | 607.225169 | 607.225169 |
| Controller-integrated loss, mL | 607.222644 | 607.222644 |
| Minimum LV volume, mL | 87.196523 | 87.196523 |
| Peak aortic ejection, mL/s | 591.992136 | 591.992136 |
| Completed controller cycles | 91 | 91 |

The fixed timestep is 0.00032877189257 s; the solver stops at the first accepted
step at or beyond 60 s. The observed full-solve NumPy speedup is **1.591x**.
There was one sequential run per backend with BLAS/OMP threads fixed to one.
These timings include the entire 1D solve and adapter instrumentation. Native
C++ runs through its validation worker; NumPy performs circuit calls in the
Starfish process and launched **zero netlist child processes**. The launcher
uses a fresh process for each simulation. Timing does not establish pure IPC cost.

Both backends use controllers at `iter_init`, frozen trial solves, and one
accepted history advance per timestep. Controller histories come from each
backend's actual state. Physical loss integrates accepted outlet flow;
controller loss integrates positive previous-published flow. Their one-sample
difference is expected.

## Agreement and strict test status

The results agree closely, but the full comparison **does not pass the retained
strict tolerances**. No tolerances were relaxed after observing the results.

| Quantity | Maximum absolute difference |
| --- | ---: |
| Any vessel pressure | 5.46966e-7 Pa |
| Any vessel flow | 9.48811e-14 m³/s |
| Any circuit pressure | 2.96125e-5 Pa |
| Any circuit flow | 5.116e-14 m³/s |
| LV volume | 1.41701e-15 m³ |
| Heart rate | 2.01936e-11 bpm |
| Physical cumulative lost volume | 1.12562e-15 m³ |
| Controller elastance | 0.00692411 Pa/m³ |

The largest circuit pressure difference occurs at heart node 2 around 59.906 s;
it is approximately 2.22e-7 mmHg. The strict comparison uses rtol=5e-11 with
pressure atol=1e-8 Pa, flow/volume atol=1e-12 in SI units and area atol=1e-14 m².
Failed physical datasets are the pressures in vessels 1 and 2, downstream
pressures and heart pressures. Monitor checks for aortic pressure, LV pressure
and elastance also exceed their thresholds. Full errors and RMSE are preserved.

Both backends pass the local physical checks: interface matching, shared-node
pressure continuity, KCL, LV and venous-capacitor history updates, controller
loss recurrence, positive vessel areas, nonnegative pressures and LV volumes,
and actual cardiac ejection/cycling. Shared KCL residuals are at most about
1.01e-18 m³/s. **All 39 netlist regression tests passed** in 5.144 s.

## Volume conservation limitation

The tracked storage is

$$
S=\sum_v\int_0^{L_v} A_v(x)\,dx+V_{LV}
  +\sum_b C_b(P_b-P_{b,ref})+C_{ven}(P_{ven}-P_{ven,ref}).
$$

This includes compliant storage relative to fixed references; it is not a
calibrated total blood volume. Vessel integrals use trapezoidal quadrature on
the actual saved grid. With physical accepted-flow loss

$$
L_n=\Delta t\sum_{k=1}^{n}Q_{bleed,k},\qquad
D_n=S_n-S_0+L_n,
$$

both backends have a final defect of **−115.543308 mL**, or **6.020%** of the
initial tracked storage. This is material and prevents a claim of validated
whole-system volume conservation.

The saved-data decomposition isolates the observed error:

$$
D_n=\underbrace{\Delta V_{vessels}
 -\Delta t\sum_{k=1}^n\sum_v(Q_{v,in,k}-Q_{v,out,k})}_{D_{vessel}}
 +\underbrace{\Delta t\sum_{k=1}^n
 [\sum_v(Q_{v,in,k}-Q_{v,out,k})-Q_{external,net,k}]}_{D_{junction}}
 +R_{circuit}.
$$

Here external net inflow to the 1D tree is aortic inflow minus both systemic-bed
outflows and hemorrhage outflow. At the end of the C++ run:

- Vessel continuity defect: −115.543308 mL.
- Integrated internal junction imbalance: approximately −1.08e-9 mL.
- Maximum circuit-storage balance residual: 7.68e-10 mL.

NumPy gives the same localization. Vessel 2 contributes approximately −61.209 mL
and vessel 3 approximately −35.081 mL. These are measured volume-versus-endpoint-
flow discrepancies in the existing 1D calculation. The decomposition does not
identify the precise numerical cause or establish convergence.

The next conservation work should examine the existing pressure-based
MacCormack field update, area reconstruction, endpoint treatment and volume
quadrature. A spatial/timestep refinement study with this same ledger is needed.
Backend agreement and local circuit residuals alone cannot answer that question.

## Preservation and scope

Source-manifest hashes still match the original tutorial and upstream 0D inputs.
All eight retained legacy C++ integration source files match HEAD byte for byte.
Mixed connected-return/independent-drain support was added to the Python adapter
and the separate validation worker. No upstream netlist_py source was changed.
The original tutorial case and old C++ integration remain available.

This completes the requested example runs and monitoring. It demonstrates
working 1D recirculation with external hemorrhage and matching controller
lifecycle. Whole-system volume conservation and strict long-run numerical
equivalence remain unresolved validation items.
