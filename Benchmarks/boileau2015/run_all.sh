#!/bin/bash
# Run every benchmark case with every field scheme, longest jobs first.
# Usage: run_all.sh <python> <casesdir> <resultsdir> [parallel jobs]
PY=$1; CASES=$2; OUT=$3; JOBS=${4:-9}
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT"
SCHEMES="MacCormack_Flux MacCormack_Matrix LaxWendroff TaylorGalerkin FV_MUSCL_HLL FV_MUSCL_Rusanov MUSCL_Hancock ADER3 DG_P2"
{
  for c in adan56 artery37; do for s in DG_P2 ADER3; do echo "$c $s"; done; done
  for c in adan56 artery37; do for s in $SCHEMES; do case $s in DG_P2|ADER3) ;; *) echo "$c $s";; esac; done; done
  for c in aorticBifurcation uta cca singlePulse_viscous singlePulse_inviscid; do for s in $SCHEMES; do echo "$c $s"; done; done
} | xargs -P "$JOBS" -L 1 bash -c '
  c=$0; s=$1
  [ -f "'"$OUT"'/${c}_${s}.npz" ] && exit 0
  (cd "'"$OUT"'" && "'"$PY"'" "'"$HERE"'/run_case.py" "'"$CASES"'/$c/$c.xml" $s "'"$OUT"'/${c}_${s}.npz" > "'"$OUT"'/log_${c}_${s}.txt" 2>&1)
  echo "$(date +%H:%M:%S) $c $s exit $? $(tail -1 "'"$OUT"'/log_${c}_${s}.txt" | cut -c1-120)"
'
