#!/usr/bin/env python3
"""Compare the retained C++ worker and the production NumPy netlist adapter.

Validation only: this is the sole place that selects the old C++ backend.
Circuit replay supplies the same explicit external Q (or P when blocked)
to both solvers, with no generated replacement domain. The synthetic input is
Q_n=scale*(1+.25*sin(n*.37+slot)), reversed every four steps for diode tests;
blocked ports receive P=+/-1000 and Q=0. SI STARFiSh fixtures use scale=1e-5
m^3/s; archived netlist_py fixtures retain their original consistent units.
Full 1D comparisons instead use the cases' existing inlet CSV/heart law and
the STARFiSh characteristic solve. These are numerical regression checks, not
long physiological or performance validations.
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext, redirect_stderr, redirect_stdout
import json
import logging
import math
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch
import xml.etree.ElementTree as ET

import h5py
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from UtilityLib.crimsonNetlistAdapter import CrimsonNetlistAdapter
from UtilityLib.netlistPyAdapter import NetlistPyAdapter, netlist_source_directory


RTOL = 5e-11
ATOL = {"slope": 1e-6, "pressure": 1e-8, "flow": 1e-12,
        "volume": 1e-12, "area": 1e-14, "time": 1e-14}


def compare(actual, expected, quantity):
    actual, expected = np.asarray(actual), np.asarray(expected)
    np.testing.assert_allclose(actual, expected, rtol=RTOL, atol=ATOL[quantity],
                               equal_nan=False, err_msg=quantity)
    return float(np.max(np.abs(actual - expected), initial=0.0))


def compare_history(cpp, reference, steps):
    cpp_files = sorted(cpp.glob("netlist*.dat"))
    if {p.name for p in cpp_files} != {p.name for p in reference.glob("netlist*.dat")}:
        raise AssertionError("netlist history filenames differ")
    errors = {"pressure": 0.0, "flow": 0.0, "volume": 0.0}
    for path in cpp_files:
        old = np.loadtxt(path, ndmin=2)
        new = np.loadtxt(reference / path.name, ndmin=2)
        if old.shape != new.shape or old.shape[0] != steps + 1:
            raise AssertionError("history row/column mismatch in {}: {} / {}; expected {} rows".format(
                path.name, old.shape, new.shape, steps + 1))
        np.testing.assert_array_equal(old[:, 0], np.arange(steps + 1))
        np.testing.assert_array_equal(new[:, 0], old[:, 0])
        quantity = ("pressure" if "Pressures" in path.name else
                    "flow" if "Flows" in path.name else "volume")
        errors[quantity] = max(errors[quantity], compare(new[:, 1:], old[:, 1:], quantity))
    return errors


def replay(name, source, directory, worker, steps, reverse=False, diode=False,
           alfi=1.0, scale=1e-5):
    case = directory / name
    case.mkdir()
    tree = ET.parse(source)
    if reverse:
        component = tree.getroot().find("./circuit/components/component")
        start, end = component.find("startNodeIndex"), component.find("endNodeIndex")
        start.text, end.text = end.text, start.text
    tree.write(case / "netlist_surfaces.xml")
    for script in source.parent.glob("*.py"):
        shutil.copyfile(script, case / script.name)
    count = len(tree.getroot().findall("circuit"))
    surfaces = [0, 7, 42][:count]
    if count > len(surfaces):
        raise ValueError("add explicit surface mapping for this validation fixture")
    cpp_dir, ref_dir = case / "cpp", case / "reference"
    cpp_dir.mkdir()
    ref_dir.mkdir()
    dt = .001
    old = CrimsonNetlistAdapter(case / "netlist_surfaces.xml", delt=dt, alfi=alfi,
        surface_ids=surfaces, output_directory=cpp_dir, worker_executable=worker)
    new = NetlistPyAdapter(case / "netlist_surfaces.xml", delt=dt, alfi=alfi,
        surface_ids=surfaces, output_directory=ref_dir)
    errors = {"slope": 0.0, "pressure": 0.0}
    old_trace, new_trace, modes = [], [], set()
    previous_modes, transition_flag_differences = {}, 0
    try:
        old.load()
        new.load()
        for n in range(steps):
            time = (n + 1) * dt
            accepted = []
            for slot, surface in enumerate(surfaces):
                sign = (-1.0 if (n // 4) % 2 else 1.0) if diode else 1.0
                flow = sign * scale * (1.0 + .25 * math.sin(n * .37 + slot))
                cpp_data = old.compute_interface_data(surface, n, time, dt, flow)
                ref_data = new.compute_interface_data(surface, n, time, dt, flow)
                if cpp_data[0] != ref_data[0]:
                    raise AssertionError("{} step {} surface {} status {} != {}".format(
                        name, n, surface, cpp_data[:2], ref_data[:2]))
                expected_changed = surface in previous_modes and previous_modes[surface] != ref_data[0]
                if ref_data[1] != expected_changed:
                    raise AssertionError("NumPy interface transition flag disagrees with the event sequence")
                if cpp_data[1] != ref_data[1]:
                    # CircuitData.cxx:575-580 resets the flag, then returns the
                    # reset value instead of returnVal. STARFiSh discards this
                    # diagnostic; compare real modes/events and all histories.
                    if cpp_data[1] or not expected_changed:
                        raise AssertionError("unexpected C++/NumPy transition flag difference")
                    transition_flag_differences += 1
                previous_modes[surface] = ref_data[0]
                modes.add(bool(cpp_data[0]))
                if cpp_data[0]:
                    errors["slope"] = max(errors["slope"], compare(ref_data[2], cpp_data[2], "slope"))
                    errors["pressure"] = max(errors["pressure"], compare(ref_data[3], cpp_data[3], "pressure"))
                    # Exercise a second probe and the full-dt coefficient getter.
                    repeated = new.compute_interface_data(surface, n, time, dt, -flow)
                    compare(repeated[2], ref_data[2], "slope")
                    compare(repeated[3], ref_data[3], "pressure")
                    cpp_update = old.compute_update_coefficients(surface, n, time, dt, flow)
                    ref_update = new.compute_update_coefficients(surface, n, time, dt, flow)
                    errors["slope"] = max(errors["slope"], compare(ref_update[0], cpp_update[0], "slope"))
                    errors["pressure"] = max(errors["pressure"], compare(ref_update[1], cpp_update[1], "pressure"))
                    pressure = cpp_data[2] * flow + cpp_data[3]
                else:
                    if not all(math.isnan(v) for v in (*cpp_data[2:], *ref_data[2:])):
                        raise AssertionError("blocked coefficients must be inactive")
                    pressure, flow = sign * 1000.0, 0.0
                accepted.append((surface, pressure, flow))
                old_trace.append((n, surface, *cpp_data, pressure, flow))
                new_trace.append((n, surface, *ref_data, pressure, flow))
            old.update_state_all_and_finalize(n, time, dt, accepted)
            new.update_state_all_and_finalize(n, time, dt, accepted)
    finally:
        try:
            old.close()
        finally:
            new.close()
    if diode and modes != {False, True}:
        raise AssertionError("diode comparison did not exercise both interface modes")
    if name == "bleed_controller_trigger" and old_trace[0][4] == old_trace[-len(surfaces)][4]:
        raise AssertionError("bleed comparison did not exercise its timed parameter change")
    errors["history"] = compare_history(cpp_dir, ref_dir, steps)
    for label, values in (("cpp", old_trace), ("reference", new_trace)):
        np.savetxt(case / (label + "_trace.csv"), values, delimiter=",",
                   header="step,surface,flow_permitted,type_changed,dp_dq,Hop,accepted_pressure,accepted_flow")
    return {"name": name, "kind": "identical-port replay", "steps": steps,
            "surfaces": surfaces, "alfi": alfi, "max_abs_error": errors,
            "transition_flag_differences": transition_flag_differences,
            "transition_flag_note": ("Retained C++ getter resets and returns false; "
                                     "NumPy reports actual mode changes. Active modes match."),
            "input": "Q=scale*(1+.25*sin(step*.37+slot)); scale={}; {}".format(
                scale, "sign reverses every 4 steps; blocked P=+/-1000, Q=0" if diode else "positive flow"),
            "status": "passed"}


def one_d_case(name, source, directory, worker, duration, resistor=False, heart=False):
    import solver
    import UtilityLib.netlistPyAdapter as adapter_module

    case = directory / name
    case.mkdir()
    for path in source.iterdir():
        if path.is_file() and path.suffix in (".xml", ".csv", ".py"):
            shutil.copyfile(path, case / path.name)
    tree = ET.parse(case / "input.xml")
    tree.getroot().find("./simulationContext/totalTime").text = str(duration)
    tree.getroot().find("./simulationContext/timeSaveBegin").text = "0.0"
    tree.write(case / "input.xml")
    if resistor:
        tree = ET.parse(ROOT / "ext/tests/passive/netlist_surfaces.xml")
        tree.getroot().find("./circuit/components/component/parameterValue").text = "133320000"
        tree.write(case / "netlist_surfaces.xml")
    if heart:
        # The copied case contains both legacy .py and modern _reference.py.
        # They use the same SI law; only the legacy script writes diagnostics.
        if not (case / "elastanceController_reference.py").is_file():
            raise FileNotFoundError("heart validation needs the paired reference controller")
    outputs = {}
    for label in ("cpp", "reference"):
        target = case / label
        target.mkdir()
        # Validation-only substitution. Production always constructs NumPy.
        def cpp_factory(*args, **kwargs):
            return CrimsonNetlistAdapter(*args, worker_executable=worker, **kwargs)
        selection = patch.object(adapter_module, "NetlistPyAdapter", cpp_factory) if label == "cpp" else nullcontext()
        with (selection, (target / "solver.log").open("w") as log,
              redirect_stdout(log), redirect_stderr(log)):
            solver.run_case(str(case / "input.xml"), str(target), "comparison", "001",
                            "netlist C++ versus NumPy validation")
        outputs[label] = target / "SolutionData_001"
    errors, datasets = {"pressure": 0., "flow": 0., "area": 0.}, 0
    with (h5py.File(outputs["cpp"] / "comparison.hdf5", "r") as old,
          h5py.File(outputs["reference"] / "comparison.hdf5", "r") as new):
        names = []
        old.visititems(lambda name, item: names.append(name) if isinstance(item, h5py.Dataset)
                       and name.rsplit("/", 1)[-1] in ("Psol", "Qsol", "Asol") else None)
        if not names:
            raise AssertionError("no vessel datasets were compared")
        for dataset in names:
            quantity = {"Psol": "pressure", "Qsol": "flow", "Asol": "area"}[dataset.rsplit("/", 1)[-1]]
            errors[quantity] = max(errors[quantity], compare(new[dataset][...], old[dataset][...], quantity))
            datasets += 1
    first_history = next(outputs["cpp"].glob("netlistPressures_surface_*.dat"))
    steps = np.loadtxt(first_history, ndmin=2).shape[0] - 1
    errors["history"] = compare_history(outputs["cpp"], outputs["reference"], steps)
    return {"name": name, "kind": "complete STARFiSh 1D solve", "duration_s": duration,
            "steps": steps, "vessel_datasets": datasets, "max_abs_error": errors,
            "input": "existing case inlet CSV" if not heart else "existing SI heart elastance law",
            "status": "passed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--worker", type=Path, default=ROOT / "ext/build/crimson_netlist_worker")
    parser.add_argument("--steps", type=int, default=64)
    parser.add_argument("--duration", type=float, default=1.0)
    parser.add_argument("--skip-1d", action="store_true")
    args = parser.parse_args()
    if args.steps < 8 or not math.isfinite(args.duration) or args.duration <= 0:
        parser.error("steps must be >=8 and duration must be positive and finite")
    output = (args.output_dir.resolve() if args.output_dir else
              Path(tempfile.mkdtemp(prefix="starfish-netlist-comparison-")))
    output.mkdir(parents=True, exist_ok=True)
    netlist = netlist_source_directory().parent
    replay_cases = [
        ("resistor", ROOT / "ext/tests/passive/netlist_surfaces.xml", {}),
        ("reversed_resistor", ROOT / "ext/tests/passive/netlist_surfaces.xml", {"reverse": True}),
        ("rcr_si", ROOT / "examples/baseline_netlist_wk3/netlist_surfaces.xml", {}),
        ("rcr_alpha", ROOT / "examples/baseline_netlist_wk3/netlist_surfaces.xml", {"alfi": .6}),
        ("multi_rcr_si", ROOT / "examples/bifurcation_netlist/wk_new/netlist_surfaces.xml", {}),
        ("mixed_rc_l_fixed_flow", netlist / "tests/fixtures/mixed_linear_history/netlist_surfaces.xml", {"scale": 3.0}),
        ("diodes", netlist / "tests/fixtures/pure_diode/netlist_surfaces.xml", {"diode": True}),
        ("pressure_chambers", netlist / "tests/fixtures/lv_full_solver/netlist_surfaces.xml", {"scale": 3.0}),
        ("plain_volume_trackers", netlist / "tests/fixtures/pure_volume_tracker/netlist_surfaces.xml", {"scale": 3.0}),
        ("bleed_controller_trigger", netlist / "tests/fixtures/bleed_coupled/netlist_surfaces.xml", {"steps": 1604, "scale": 3.0}),
        ("doubling_controller", ROOT / "ext/tests/controllers/netlist_surfaces.xml", {"steps": 8}),
    ]
    results = []
    for name, source, options in replay_cases:
        steps = options.pop("steps", args.steps)
        try:
            result = replay(name, source, output, str(args.worker.resolve()), steps, **options)
        except Exception as exc:
            result = {"name": name, "status": "failed", "error": repr(exc)}
        results.append(result)
        print(name + ": " + result["status"], flush=True)
    if not args.skip_1d:
        logging.getLogger("starfish").setLevel(logging.WARNING)
        for name, source, options in (
            ("single_vessel_resistor", ROOT / "examples/baseline_netlist_wk3", {"resistor": True}),
            ("single_vessel_rcr", ROOT / "examples/baseline_netlist_wk3", {}),
            ("bifurcation_rcr", ROOT / "examples/bifurcation_netlist/wk_new", {}),
            ("bifurcation_heart", ROOT / "examples/bifurcation_heart_netlist", {"heart": True}),
        ):
            try:
                result = one_d_case(name, source, output, str(args.worker.resolve()), args.duration, **options)
            except Exception as exc:
                result = {"name": name, "status": "failed", "error": repr(exc)}
            results.append(result)
            print(name + ": " + result["status"], flush=True)
    report = {"python": sys.version, "numpy": np.__version__, "netlist_source": str(netlist),
              "worker": str(args.worker.resolve()), "rtol": RTOL, "atol": ATOL,
              "results": results, "passed": all(r["status"] == "passed" for r in results)}
    report_path = output / "comparison.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print("Report: " + str(report_path))
    if not report["passed"]:
        for result in results:
            if result["status"] == "failed":
                print(result["name"] + ": " + result["error"])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
