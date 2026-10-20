#!/usr/bin/env python3
"""Run each example as configured: retained C++ first, then NumPy/reference.

Every run uses a private input snapshot and a new result directory inside the
original case. No input physics, durations, old outputs, or legacy controllers
are changed. C++ failures skip the paired Python run. Native and constant-law
controls are reported separately from cases exercising the circuit adapters.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
from unittest.mock import patch
import xml.etree.ElementTree as ET

import h5py
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RTOL = 5e-11
ATOL = {"pressure": 1e-8, "flow": 1e-12, "volume": 1e-12,
        "area": 1e-14, "time": 1e-14}
OUTPUT_NAME = "results_netlist_comparison"


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def worker_run(source, backend, target):
    """A fresh process isolates singleton managers and backend selection."""
    import solver
    import SolverLib.class1DflowSolver as flow_module
    import UtilityLib.netlistPyAdapter as adapter_module

    result = {"backend": backend, "status": "running", "input": str(source),
              "wall_seconds": None, "initialization_seconds": None,
              "solve_seconds": None, "netlist_calls": {}, "netlist_seconds": 0.0}
    solver._configure_logging(str(target))
    logger = logging.getLogger("starfish")
    # Suppress per-step progress on disk; retain INFO configuration and timings.
    # The solver's progress printer still writes to the captured console log.
    for handler in logger.handlers:
        handler.setLevel(logging.INFO)
    original_solver = flow_module.FlowSolver
    original_adapter = adapter_module.NetlistPyAdapter
    if backend == "cpp":
        from UtilityLib.crimsonNetlistAdapter import CrimsonNetlistAdapter
        selected_adapter = CrimsonNetlistAdapter
    else:
        selected_adapter = original_adapter

    def account(name, elapsed):
        value = result["netlist_calls"].setdefault(name, {"calls": 0, "seconds": 0.0})
        value["calls"] += 1
        value["seconds"] += elapsed
        result["netlist_seconds"] += elapsed

    class ProfiledAdapter:
        def __init__(self, *args, **kwargs):
            started = time.perf_counter()
            try:
                self.actual = selected_adapter(*args, **kwargs)
            finally:
                account("construct", time.perf_counter() - started)

        def __getattr__(self, name):
            value = getattr(self.actual, name)
            if not callable(value):
                return value

            def measured(*args, **kwargs):
                started = time.perf_counter()
                try:
                    return value(*args, **kwargs)
                finally:
                    account(name, time.perf_counter() - started)
            return measured

    class TimedFlowSolver(original_solver):
        def __init__(self, *args, **kwargs):
            started = time.perf_counter()
            try:
                super().__init__(*args, **kwargs)
            finally:
                result["initialization_seconds"] = time.perf_counter() - started
            original_solve = self.solve

            def measured_solve(*args, **kwargs):
                started = time.perf_counter()
                try:
                    return original_solve(*args, **kwargs)
                finally:
                    result["solve_seconds"] = time.perf_counter() - started
            self.solve = measured_solve

    started = time.perf_counter()
    try:
        with ExitStack() as stack:
            stack.enter_context(patch.object(adapter_module, "NetlistPyAdapter", ProfiledAdapter))
            stack.enter_context(patch.object(flow_module, "FlowSolver", TimedFlowSolver))
            output_hdf5, output_xml, _ = solver.run_case(
                str(source), str(target), "solution", "001",
                "Example comparison: " + backend + " netlist", export_ascii=False)
        result.update(status="completed", hdf5=output_hdf5, output_xml=output_xml)
    except BaseException as exc:
        result.update(status="failed", error=str(exc), exception_type=type(exc).__name__,
                      traceback=traceback.format_exc())
        traceback.print_exc()
    finally:
        result["wall_seconds"] = time.perf_counter() - started
        result["uses_circuit_adapter"] = bool(result["netlist_calls"])
        save_json(target / "run.json", result)
    return 0 if result["status"] == "completed" else 1


def discover(examples):
    paths = []
    for path in examples.rglob("*.xml"):
        parts = path.relative_to(examples).parts[:-1]
        if any(part == "results" or part == OUTPUT_NAME or part == "__pycache__"
               or part.startswith("SolutionData_") for part in parts):
            continue
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        if root.find("vessels") is not None:
            paths.append(path.resolve())
    return sorted(paths)


def snapshot(source, destination):
    destination.mkdir()
    hashes = {}
    for path in sorted(source.parent.iterdir()):
        if not path.is_file() or path.suffix.lower() not in (".xml", ".csv", ".py", ".dat"):
            continue
        if path.name.startswith(("netlistPressures_", "netlistFlows_", "netlistVolumes_")) or path.name.endswith("_history.dat"):
            continue
        shutil.copyfile(path, destination / path.name)
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return destination / source.name, hashes


def classify(source):
    root = ET.parse(source).getroot()
    boundaries = root.findall("./boundaryConditions/boundaryCondition/*")
    netlists = [b for b in boundaries if b.tag in ("Netlist", "_Netlist")]
    real = [b for b in netlists if b.findtext("Rtilde", "None").strip() == "None"]
    issues = []
    for boundary in boundaries:
        if boundary.tag in ("Flow-FromFile", "Pressure-FromFile"):
            filename = boundary.findtext("filePathName")
            if filename and not (source.parent / filename).is_file():
                fallbacks = [p for p in source.parent.iterdir() if p.is_file()
                             and p.name.lower().endswith(".csv")
                             and "inflow" in p.name.lower() and ":" not in p.name]
                preferred = [p for p in fallbacks if "_template" not in p.name]
                if len(preferred) == 1:
                    fallbacks = preferred
                if len(fallbacks) == 1:
                    issues.append("Declared waveform path {} is unavailable; Starfish uses local fallback {}.".format(
                        filename, fallbacks[0].name))
                else:
                    issues.append("Missing declared waveform: " + filename)
    if real and not (source.parent / "netlist_surfaces.xml").is_file():
        issues.append("Missing netlist_surfaces.xml")
    for endpoint in root.findall("./boundaryConditions/boundaryCondition"):
        outlets = [b.tag for b in endpoint if b.tag.startswith("_")]
        if len(outlets) > 1:
            issues.append("Vessel {} declares multiple outlet conditions: {}".format(
                endpoint.get("vesselId"), ", ".join(outlets)))
    notes = source.parent / "netlist_comparison_notes.md"
    return {"configured_duration_s": float(root.findtext("./simulationContext/totalTime")),
            "vessels": len(root.findall("./vessels/vessel")),
            "input_issues": issues,
            "comparison_notes": notes.read_text().strip() if notes.is_file() else "",
            "model": "circuit netlist" if real else "constant netlist law" if netlists else "native Starfish control"}


def run_backend(source, label, run):
    target = run / label
    target.mkdir()
    copied_input, hashes = snapshot(source, target / "inputs")
    environment = dict(os.environ)
    environment.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
                       PYTHONDONTWRITEBYTECODE="1")
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "--run-case",
               str(copied_input), "--backend", label, "--target", str(target)]
    started = time.perf_counter()
    with (target / "console.log").open("w") as log:
        process = subprocess.run(command, cwd=target, env=environment, stdout=log,
                                 stderr=subprocess.STDOUT)
    elapsed = time.perf_counter() - started
    metadata = target / "run.json"
    result = json.loads(metadata.read_text()) if metadata.is_file() else {
        "status": "failed", "error": "process failed before writing run metadata; see console.log"}
    result.update(process_returncode=process.returncode, process_wall_seconds=elapsed,
                  source_hashes=hashes, console_log=str(target / "console.log"))
    save_json(metadata, result)
    return result


def metric(actual, expected, quantity):
    if actual.shape != expected.shape:
        raise ValueError("{} array shapes differ: {} versus {}".format(quantity, actual.shape, expected.shape))
    if not np.isfinite(actual).all() or not np.isfinite(expected).all():
        raise ValueError("nonfinite {} output".format(quantity))
    error = np.abs(actual - expected)
    max_abs = float(np.max(error, initial=0.0))
    scale = float(np.max(np.abs(expected), initial=0.0))
    return {"max_abs": max_abs, "rmse": float(np.sqrt(np.mean(error * error))) if error.size else 0.0,
            "max_abs_over_cpp_peak": max_abs / scale if scale else (0.0 if max_abs == 0 else None),
            "samples": int(error.size),
            "within_tolerance": bool(np.all(error <= ATOL[quantity] + RTOL * np.abs(expected)))}


def compare_outputs(cpp, python):
    metrics = {"vessels": {}, "netlist": {}, "time": {}}
    with h5py.File(cpp["hdf5"], "r") as old, h5py.File(python["hdf5"], "r") as new:
        old_names, new_names = [], []
        for file, names in ((old, old_names), (new, new_names)):
            file.visititems(lambda name, item: names.append(name) if isinstance(item, h5py.Dataset) else None)
        if set(old_names) != set(new_names):
            raise ValueError("HDF5 dataset names differ")
        for name in old_names:
            leaf = name.rsplit("/", 1)[-1]
            kind = {"Psol": "pressure", "Qsol": "flow", "Asol": "area"}.get(leaf)
            if kind:
                metrics["vessels"][name] = dict(quantity=kind, **metric(new[name][...], old[name][...], kind))
            elif "time" in leaf.lower() and np.issubdtype(old[name].dtype, np.number):
                metrics["time"][name] = dict(quantity="time", **metric(new[name][...], old[name][...], "time"))
        if not metrics["vessels"]:
            raise ValueError("no P/Q/A vessel arrays in output")
    old_dir, new_dir = Path(cpp["hdf5"]).parent, Path(python["hdf5"]).parent
    old_files = {p.name for p in old_dir.glob("netlist*.dat")}
    new_files = {p.name for p in new_dir.glob("netlist*.dat")}
    if old_files != new_files:
        raise ValueError("netlist history filenames differ")
    for name in sorted(old_files):
        a, b = np.loadtxt(old_dir / name, ndmin=2), np.loadtxt(new_dir / name, ndmin=2)
        if a.shape != b.shape or not np.array_equal(a[:, 0], b[:, 0]):
            raise ValueError("history shapes or accepted step indices differ: " + name)
        kind = "pressure" if "Pressures" in name else "flow" if "Flows" in name else "volume"
        metrics["netlist"][name] = dict(quantity=kind, accepted_steps=a.shape[0]-1,
                                        **metric(b[:, 1:], a[:, 1:], kind))
    metrics["passed"] = all(row["within_tolerance"] for group in ("vessels", "netlist", "time")
                            for row in metrics[group].values())
    return metrics


def peak(metrics, group, quantity):
    return max((row["max_abs"] for row in metrics.get(group, {}).values()
                if row["quantity"] == quantity), default=0.0)


def number(value):
    return "—" if value is None else "{:.4g}".format(value)


def case_markdown(row):
    lines = ["# Example C++ / NumPy comparison", "", "Input: `{}`".format(row["source"]),
             "", "Status: **{}**".format(row["status"]), "",
             "Model: {}; configured duration: {} s; vessels: {}.".format(
                 row["model"], row["configured_duration_s"], row["vessels"]), ""]
    if row.get("reason"):
        lines += ["Reason: " + row["reason"], ""]
    if row.get("input_issues"):
        lines += ["Input observations:", ""]
        lines += ["- " + issue for issue in row["input_issues"]]
        lines += [""]
    if row.get("comparison_notes"):
        lines += [row["comparison_notes"], ""]
    lines += ["Both backends use private, identical input snapshots with the original duration.",
              "C++ is run first. C++ failures skip the Python comparison.",
              "Native controls and constant coefficient boundaries do not execute circuit adapters.", "",
              "## Timing", "", "| Measurement (seconds) | C++ | NumPy |", "| --- | ---: | ---: |"]
    for key, label in (("solve_seconds", "Starfish solve"), ("initialization_seconds", "Solver initialization"),
                       ("netlist_seconds", "Cumulative circuit adapter calls"),
                       ("wall_seconds", "Run including output and adapter shutdown"),
                       ("process_wall_seconds", "Whole process including imports")):
        lines.append("| {} | {} | {} |".format(label, number(row.get("cpp", {}).get(key)),
                                               number(row.get("python", {}).get(key))))
    lines += ["", "Sequential fresh processes; BLAS/OMP thread counts set to 1 for both backends.",
              "One run each; these are observed timings, not repeated benchmark estimates.",
              "The solver's initialization ramp, when enabled by the original case, is included in solve time.",
              "C++ adapter timing includes IPC and worker startup/shutdown. Adapter methods are measured",
              "at their outer boundary; their time is also included in the whole run.", ""]
    metrics = row.get("accuracy")
    if metrics:
        lines += ["## Numerical agreement", "", "Differences are NumPy versus C++ with matching sample indices;",
                  "they measure implementation agreement, not absolute physiological accuracy.", "",
                  "| Output | Maximum absolute difference | Units |", "| --- | ---: | --- |"]
        for group, quantity, label, unit in (("vessels", "pressure", "Vessel pressure", "Pa"),
                ("vessels", "flow", "Vessel flow", "m³/s"), ("vessels", "area", "Vessel area", "m²"),
                ("netlist", "pressure", "Netlist pressure", "Pa"), ("netlist", "flow", "Netlist flow", "m³/s"),
                ("netlist", "volume", "Netlist volume", "m³")):
            present = any(r["quantity"] == quantity for r in metrics[group].values())
            lines.append("| {} | {} | {} |".format(label, number(peak(metrics, group, quantity)) if present else "not used", unit))
        lines += ["", "Tolerance: rtol={}, pressure atol={} Pa, flow/volume atol={} m³/s or m³,".format(
            RTOL, ATOL["pressure"], ATOL["flow"]), "area atol={} m². Nonfinite output, missing datasets and mismatched steps fail.".format(ATOL["area"]),
            "Full per-dataset maximum error, RMSE, normalized peak error, sample counts and timing call counts",
            "are in `comparison.json`.", ""]
    lines += ["## Files", "", "- `cpp/`: retained worker outputs, input snapshot, logs and timing metadata.",
              "- `python/`: NumPy outputs, input snapshot, logs and timing metadata (when C++ succeeded).",
              "- Each successful backend stores HDF5/XML and netlist DAT files in `SolutionData_001/`.", ""]
    return "\n".join(lines)


def summary_markdown(rows, skipped_assets, examples=ROOT / "examples"):
    passed = sum(r["status"] == "passed" for r in rows)
    skipped = sum(r["status"] == "skipped_cpp_failed" for r in rows)
    lines = ["# Example cases: C++ versus NumPy netlists", "",
             "{} passed; {} skipped because C++ failed; {} other failures.".format(
                 passed, skipped, len(rows)-passed-skipped), "",
             "All original configured durations and input physics were retained. Results are stored",
             "inside each case under `results_netlist_comparison/`. Older results were retained.", "",
             "| Case | Model | Duration (s) | Status | C++ solve (s) | NumPy solve (s) | C++/NumPy solve ratio | Max vessel ΔP (Pa) | Report |",
             "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- |"]
    for row in rows:
        cpp_t = row.get("cpp", {}).get("solve_seconds")
        py_t = row.get("python", {}).get("solve_seconds")
        ratio = cpp_t / py_t if cpp_t is not None and py_t else None
        path = Path(row["run_directory"]) / "comparison.md"
        relative = os.path.relpath(path, examples).replace(" ", "%20")
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | [details]({}) |".format(
            row["case"], row["model"], number(row["configured_duration_s"]), row["status"],
            number(cpp_t), number(py_t), number(ratio),
            number(peak(row["accuracy"], "vessels", "pressure")) if "accuracy" in row else "—", relative))
    lines += ["", "The case reports include netlist pressure/flow/volume errors, vessel P/Q/A errors,",
              "initialization, whole-run, whole-process and circuit-adapter timings. Native controls",
              "and constant-law controls are labelled and do not measure a C++/NumPy circuit backend.",
              "Both backends run sequentially in fresh processes with BLAS/OMP threads set to 1.",
              "Times are single-run observations. A ratio above 1 means NumPy had the shorter solve.",
              "Agreement is checked at rtol={} and the physical absolute tolerances documented per case.".format(RTOL), ""]
    lines += ["## Circuit netlist accuracy and adapter timing", "",
              "These rows exercise the actual C++ and NumPy circuit implementations. Adapter time",
              "includes requests, circuit updates, startup/shutdown, and C++ IPC. Native and",
              "constant-law controls are excluded from this table.", "",
              "| Case | Max netlist ΔP (Pa) | Max netlist ΔQ (m³/s) | Max netlist ΔV (m³) | C++ adapter (s) | NumPy adapter (s) |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in rows:
        if row["model"] != "circuit netlist" or "accuracy" not in row:
            continue
        lines.append("| {} | {} | {} | {} | {} | {} |".format(row["case"],
            *(number(peak(row["accuracy"], "netlist", kind)) for kind in ("pressure", "flow", "volume")),
            number(row["cpp"]["netlist_seconds"]), number(row["python"]["netlist_seconds"])))
    lines += [""]
    noted = [row for row in rows if row.get("comparison_notes")]
    if noted:
        lines += ["## Case notes", ""]
        for row in noted:
            lines += ["### " + row["case"], "", row["comparison_notes"], ""]
    if skipped:
        lines += ["## Cases skipped after a C++ failure", ""]
        for row in rows:
            if row["status"] == "skipped_cpp_failed":
                reason = " ".join(row["reason"].splitlines())
                lines += ["- `{}`: {}".format(row["case"], reason)]
                if row.get("input_issues"):
                    lines += ["  Input observations: " + "; ".join(row["input_issues"])]
        lines += [""]
    lines += ["## Directories without a runnable network", ""]
    lines += ["- " + item for item in skipped_assets]
    reproduce = "python3 -B UnitTesting/run_example_netlist_comparisons.py"
    if examples.resolve() != (ROOT / "examples").resolve():
        import shlex
        reproduce += " --examples " + shlex.quote(os.path.relpath(examples, ROOT))
    lines += ["", "From the repository root, reproduce with `{}`.".format(reproduce),
              "Each execution allocates new per-case result directories.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-case", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--backend", choices=("cpp", "python"), help=argparse.SUPPRESS)
    parser.add_argument("--target", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--examples", type=Path, default=ROOT / "examples")
    args = parser.parse_args()
    if args.run_case:
        raise SystemExit(worker_run(args.run_case, args.backend, args.target))
    examples = args.examples.resolve()
    rows = []
    sources = list(discover(examples))
    assets = ["`{}`: supporting assets; no runnable network input XML.".format(path.name)
              for path in sorted(examples.iterdir())
              if path.is_dir() and path.name not in (OUTPUT_NAME, "__pycache__", "results")
              and not any(path in source.parents for source in sources)]
    assets.append("Branch DAT/XML exports and circuit-only XML files are supporting assets, not additional 1D input cases.")
    for source in sources:
        case_name = str(source.parent.relative_to(examples))
        if source.name != "input.xml":
            case_name += " / " + source.name
        output = source.parent / OUTPUT_NAME
        output.mkdir(exist_ok=True)
        stem = "main" if source.name == "input.xml" else "input_copy"
        index = 1
        while (output / (stem + "_{:03d}".format(index))).exists():
            index += 1
        run = output / (stem + "_{:03d}".format(index))
        run.mkdir()
        row = dict(case=case_name, source=str(source), run_directory=str(run), **classify(source))
        print("START " + case_name + " ({} s)".format(row["configured_duration_s"]), flush=True)
        row["cpp"] = run_backend(source, "cpp", run)
        if row["cpp"]["status"] != "completed":
            row.update(status="skipped_cpp_failed", reason=row["cpp"].get("error", "C++ run failed"))
        else:
            row["python"] = run_backend(source, "python", run)
            if row["python"]["status"] != "completed":
                row.update(status="failed_python", reason=row["python"].get("error", "Python run failed"))
            else:
                try:
                    row["accuracy"] = compare_outputs(row["cpp"], row["python"])
                    row["status"] = "passed" if row["accuracy"]["passed"] else "failed_accuracy"
                except Exception as exc:
                    row.update(status="failed_accuracy", reason=str(exc))
        save_json(run / "comparison.json", row)
        (run / "comparison.md").write_text(case_markdown(row))
        rows.append(row)
        save_json(examples / "netlist_cpp_python_comparison.json", {"rtol": RTOL, "atol": ATOL, "cases": rows})
        (examples / "netlist_cpp_python_comparison.md").write_text(summary_markdown(rows, assets, examples))
        print("DONE " + case_name + ": " + row["status"], flush=True)
    print("Summary: " + str(examples / "netlist_cpp_python_comparison.md"), flush=True)
    if any(row["status"] not in ("passed", "skipped_cpp_failed") for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
