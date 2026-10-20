#!/usr/bin/env python3
"""Check the copied tutorial's reference laws against its actual legacy classes."""

import importlib.util
import io
import json
from pathlib import Path
import sys
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from UtilityLib.netlistPyAdapter import netlist_source_directory

sys.path.insert(0, str(netlist_source_directory()))
CASE = ROOT / "examples/cr_sf_tutorial_demo/heart_model"


class LegacyBase:
    def __init__(self, *args):
        self.broadcasts = {}

    def finishSetup(self):
        pass

    def getRecievedBroadcastValue(self, *args):
        return self.observed_flow

    def clearBroadcastData(self):
        self.broadcasts.clear()

    def addBroadcastVariable(self, name, value):
        self.broadcasts[name] = value


def load_pair(name):
    stub = types.ModuleType("CRIMSONPython")
    stub.abstractParameterController = LegacyBase
    namespace = {}
    with patch.dict(sys.modules, CRIMSONPython=stub):
        exec(compile((CASE / (name + ".py")).read_text(), name + ".py", "exec"), namespace)
    with patch("builtins.open", lambda *args, **kwargs: io.StringIO()):
        legacy = namespace["parameterController"](name, 0)
    legacy.appendHistory = lambda *args: None
    spec = importlib.util.spec_from_file_location(name + "_tutorial_reference", CASE / (name + "_reference.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return legacy, module, module.build_controller_program()


def main():
    heart, module, program = load_pair("elastanceController")
    parameters, state = program.initialize()
    count = 0

    def check_step(state, flow, dt):
        nonlocal count
        heart.observed_flow = flow
        expected = heart.updateControl(0.0, dt, {}, {}, {})
        result = program.update(parameters, state, types.SimpleNamespace(
            dt=dt, broadcasts={"injured_vessel_flow": flow}))
        expected_state = (heart.m_periodicTime, heart.m_heartPeriod,
                          heart.totalBloodLoss, heart.currentHeartRate,
                          heart.deltaHeartRate, heart.debtDelta)
        if float(result.target_values[0]) != expected or tuple(result.state) != expected_state:
            raise AssertionError("Heart law mismatch at update {}".format(count))
        count += 1
        return result.state

    for step in range(100000):
        flow = -0.001 if step % 11 == 0 else 0.0001 * (1 + step % 7)
        state = check_step(state, flow, 0.001)
    # Exercise both physiological limits and the negative-phase clamp directly.
    for rate in (300.0, 20.0, 180.0):
        period = 60.0 / rate
        heart.m_periodicTime = period - 0.0005
        heart.m_heartPeriod = period
        heart.totalBloodLoss = 0.05
        state = module.FeedbackState(heart.m_periodicTime, period, 0.05, rate, 0.0, 0.0)
        state = check_step(state, 0.0005, 0.001)

    observer, _, observer_program = load_pair("bloodLossObserver")
    observer_parameters, observer_state = observer_program.initialize()
    observer.stepIndex = 0  # Keep its diagnostic write branch inactive.
    for flow, pressure in ((0.0, 0.0), (0.0005, 120.0), (-0.0007, -40.0)):
        expected = observer.updateControl(0.0, 0.001, {2: pressure}, {1: flow}, {})
        result = observer_program.update(observer_parameters, observer_state,
            types.SimpleNamespace(flow=[flow], pressure=[999.0, pressure]))
        if float(result.target_values[0]) != expected or result.broadcasts != observer.broadcasts:
            raise AssertionError("Observer law mismatch")
        observer_state = result.state

    report = {
        "passed": True, "heart_updates": count, "observer_updates": 3,
        "maximum_elastance_difference": 0.0, "all_six_heart_state_values_exact": True,
        "coverage": ["positive and negative bleed flow", "heart-rate upper/lower limits",
                     "negative-phase clamp", "owner-local observer indexing and broadcast"],
        "method": "Execute the copied legacy class with a CRIMSONPython API stub and diagnostic I/O suppressed; compare each update to its reference program.",
        "reproduce": "python3 -B UnitTesting/validate_tutorial_controllers.py",
    }
    destination = CASE.parent / "controller_translation_validation.json"
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
