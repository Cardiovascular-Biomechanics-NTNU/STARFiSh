# Results

Errors are in percent and follow Boileau et al. (2015), Eqs. 10–13. Pressure errors are
relative pointwise; flow errors are normalised by the reference maximum.

Files in this folder:

- `summary.txt`: per-site RMS errors for every case and scheme, with the range of the
  paper's six schemes.
- `summary.json`: the full output of `compare.py`, with RMS, MAX, SYS and DIAS per site,
  last-cycle waveforms and timings.
- `convergence.json`: the single-pulse grid convergence study.

The raw solutions (about 400 MB of `.npz` files) are not included. To regenerate them, follow
`../README.md`.

## RMS error by case

Each value is the mean over the paper's measurement sites. The references are:

- CCA, UTA and aortic bifurcation: the 3D solution.
- 37-artery: the in vitro measurements.
- ADAN56: the median of the paper's six schemes.

| Scheme | CCA P | UTA P | Aortic bif. P | 37-artery P | ADAN56 P | CCA Q | UTA Q | Aortic bif. Q | 37-artery Q | ADAN56 Q |
|---|---|---|---|---|---|---|---|---|---|---|
| MacCormack_Flux | 0.24 | 1.31 | 0.46 | 3.57 | 0.82 | 0.31 | 1.76 | 0.91 | 15.29 | 1.47 |
| MacCormack_Matrix | 0.24 | — | 0.45 | 3.31 | 2.47 | 0.30 | — | 0.92 | 15.32 | 5.65 |
| LaxWendroff | 0.27 | 1.33 | 0.47 | 3.80 | 0.95 | 0.31 | 1.73 | 0.91 | 15.32 | 1.82 |
| TaylorGalerkin | 0.23 | 1.32 | 0.27 | 3.63 | 1.72 | 0.29 | 1.81 | 0.82 | 15.42 | 3.61 |
| FV_MUSCL_HLL | 0.24 | 1.35 | 0.40 | 4.11 | 1.73 | 0.30 | 1.81 | 0.82 | 15.44 | 3.69 |
| FV_MUSCL_Rusanov | 0.25 | 1.33 | 0.36 | 3.58 | 1.75 | 0.30 | 1.81 | 0.83 | 15.42 | 3.66 |
| MUSCL_Hancock | 0.25 | 1.33 | 0.36 | 4.24 | 1.71 | 0.30 | 1.80 | 0.84 | 15.44 | 3.63 |
| ADER3 | 0.25 | 1.33 | 0.36 | 4.32 | 1.69 | 0.30 | 1.80 | 0.84 | 15.44 | 3.58 |
| DG_P2 | 0.25 | 1.32 | 0.37 | 4.99 | 1.80 | 0.30 | 1.80 | 0.84 | 15.48 | 3.84 |
| *Paper's six schemes* | 0.23–0.28 | 1.19–1.31 | 0.45–0.50 | 2.76–2.81 | 0.05–1.38 | 0.26–0.30 | 1.72–1.82 | 0.64–0.91 | 14.82–15.16 | — |

- `MacCormack_Matrix` aborts on UTA with a negative pressure in the predictor step at t ≈ 0.064 s.
- The ADAN56 flow range for the paper is left out because one scheme's flow spikes dominate it.
- On the 37-artery case, pressure errors are higher than the paper's. The paper's results
  match an outflow pressure of 0, but its Table IX gives 432.6 Pa. These runs use the value
  from Table IX.

## Port check

`MacCormack_Flux` against the paper's STARFiSh (McC) solution gives these pressure RMS
differences:

| Case | Pressure RMS difference |
|---|---|
| CCA | 0.01% |
| UTA | 0.25% |
| ADAN56 | 0.6–1.9% |

## Single pulse

Error against the paper's DG reference.

| Scheme | Inviscid RMS | Peak at 1.5 s | Viscous RMS | Peak at 1.5 s |
|---|---|---|---|---|
| MacCormack_Flux | 0.14 | +0.24 | 0.14 | +0.13 |
| MacCormack_Matrix | 0.34 | +0.03 | 0.30 | −0.02 |
| LaxWendroff | 0.12 | +0.26 | 0.12 | +0.17 |
| TaylorGalerkin | 0.03 | −0.08 | 0.03 | −0.10 |
| FV_MUSCL_HLL | 0.35 | −5.90 | 0.33 | −4.81 |
| FV_MUSCL_Rusanov | 0.35 | −5.90 | 0.33 | −4.81 |
| MUSCL_Hancock | 0.05 | −1.62 | 0.05 | −1.58 |
| ADER3 | 0.02 | −0.32 | 0.02 | −0.36 |
| DG_P2 | 0.02 | +0.11 | 0.02 | +0.06 |

The paper's six schemes have RMS errors between 0.05% and 0.53%. The limited MUSCL schemes
clip the pulse peak.

## Grid convergence

The table shows inviscid single-pulse pressure error at t = 1.5 s against the paper's DG
reference. The vessel is 10 m long, and N is the number of nodes.

| Scheme | N=401 | 801 | 1601 | 3201 | 6401 | Order 401→801 | 801→1601 | 1601→3201 | 3201→6401 |
|---|---|---|---|---|---|---|---|---|---|
| MacCormack_Flux | 6.513 | 4.829 | 2.411 | 0.810 | 0.270 | 0.43 | 1.00 | 1.57 | 1.59 |
| MacCormack_Matrix | 6.557 | 4.959 | 2.680 | 1.163 | 0.648 | 0.40 | 0.89 | 1.20 | 0.84 |
| LaxWendroff | 6.509 | 4.815 | 2.383 | 0.774 | 0.233 | 0.43 | 1.01 | 1.62 | 1.73 |
| TaylorGalerkin | 5.771 | 3.484 | 1.266 | 0.316 | 0.052 | 0.73 | 1.46 | 2.00 | 2.59 |
| FV_MUSCL_HLL | 6.619 | 5.236 | 3.197 | 1.418 | 0.619 | 0.34 | 0.71 | 1.17 | 1.20 |
| FV_MUSCL_Rusanov | 6.619 | 5.236 | 3.197 | 1.418 | 0.619 | 0.34 | 0.71 | 1.17 | 1.20 |
| MUSCL_Hancock | 4.399 | 2.203 | 0.792 | 0.251 | 0.088 | 1.00 | 1.47 | 1.66 | 1.51 |
| ADER3 | 5.223 | 3.080 | 1.029 | 0.193 | 0.029 | 0.76 | 1.58 | 2.42 | 2.72 |
| DG_P2 | 0.615 | 0.186 | 0.064 | 0.023 | 0.025 | 1.72 | 1.54 | 1.48 | −0.15 |

At the finest grid, the DG_P2 error stops falling at about 0.02%, which is probably the
accuracy of the reference solution itself.

## Solve time

Solve time in seconds, on one core per run, with nine runs in parallel on an Apple M1 Max.

| Scheme | Single pulse | CCA | UTA | Aortic bif. | 37-artery | ADAN56 |
|---|---|---|---|---|---|---|
| MacCormack_Flux | 3 | 2 | 2 | 13 | 828 | 1574 |
| MacCormack_Matrix | 3 | 2 | — | 12 | 791 | 1488 |
| LaxWendroff | 11 | 4 | 3 | 17 | 961 | 1838 |
| TaylorGalerkin | 23 | 6 | 4 | 28 | 1076 | 2185 |
| FV_MUSCL_HLL | 21 | 6 | 6 | 29 | 1672 | 3069 |
| FV_MUSCL_Rusanov | 20 | 7 | 6 | 29 | 1670 | 3082 |
| MUSCL_Hancock | 15 | 5 | 5 | 23 | 1309 | 2400 |
| ADER3 | 142 | 15 | 15 | 58 | 4097 | 6266 |
| DG_P2 | 290 | 44 | 34 | 182 | 7127 | 7658 |
