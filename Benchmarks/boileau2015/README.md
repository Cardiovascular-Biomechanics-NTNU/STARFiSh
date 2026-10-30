# Boileau et al. (2015) benchmark

Runs the six test cases of Boileau et al., *A benchmark study of numerical schemes for
one-dimensional arterial blood flow modelling*, Int J Numer Meth Biomed Eng 2015 (e02732),
with every STARFiSh field scheme, and scores the results with the paper's error metrics.

The reference data is the paper's supplementary material
(`cnm2732-sup-0001-Supplementary.zip`), which has to be downloaded by hand.

```bash
SUPP=path/to/SuppMaterial_1DBenchmark_Boileau_etal
python make_cases.py $SUPP cases            # STARFiSh networks for the six cases
./run_all.sh python cases results 9          # every case with every scheme, 9 jobs at a time
python compare.py $SUPP results cases summary.json
```

`run_case.py` runs a single case with a single scheme, without visualisation.

Notes on how the cases are set up (also in the scripts):

- STARFiSh stops on any negative pressure, so all generated cases shift pressure by
  10 kPa. Subtract it from computed pressures; `compare.py` does.
- Windkessel outlets take their outflow pressure from minus the external pressure, so the
  outflow pressure is set through `externalPressure`.
- Inflow is prescribed as increments, so the cases use `Auto` initialisation. It shifts the
  saved time axis against the inflow phase; `compare.py` measures and removes the shift.
- ADAN56 has no 3D or measured solution; it is scored against the median of the paper's
  six schemes.
