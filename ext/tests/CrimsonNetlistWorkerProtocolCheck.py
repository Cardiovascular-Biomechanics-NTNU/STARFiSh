#!/usr/bin/env python3
"""End-to-end check of the production CRIMSON worker client."""

from __future__ import annotations

import argparse
import math
import sys
import tempfile
from pathlib import Path


# CTest runs this script from its build directory. Add the repository root
# explicitly so the test imports the production client rather than duplicating
# its subprocess and protocol implementation.
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from UtilityLib.crimsonNetlistWorkerClient import (  # noqa: E402
    CrimsonNetlistWorkerClient,
)


def require_close(actual, expected, name):
    """Require an exact-scale coefficient comparison with a small tolerance."""
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1.0e-12):
        raise RuntimeError(
            "Unexpected {}: {}; expected {}".format(name, actual, expected)
        )


def run_check(worker, fixture):
    """
    Verify controller state persists across the Python 3/worker boundary.

    The fixture starts with a resistance of 100. Finalizing timestep 0 executes
    its Python 2 controller, which doubles the resistance. Timestep 1 must
    therefore return `dp_dq = 200`.
    """
    if not worker.is_file():
        raise RuntimeError("Worker executable was not found: {}".format(worker))
    if not fixture.is_file():
        raise RuntimeError(
            "Controlled netlist fixture was not found: {}".format(fixture)
        )

    client = CrimsonNetlistWorkerClient(worker_executable=worker)
    with tempfile.TemporaryDirectory(
        prefix="starfish worker protocol "
    ) as output_directory:
        try:
            controller_count = client.load(
                netlist_xml=fixture,
                output_directory=output_directory,
                hstep=10,
                alfi=1.0,
                dt=0.001,
                surface_ids=[1],
            )
            if controller_count != 1:
                raise RuntimeError(
                    "Expected one CRIMSON controller; received {}".format(
                        controller_count
                    )
                )

            client.start_timestep(0, 0.001, 0.001)
            interface_data_0 = client.compute_interface_data(
                1,
                0,
                0.001,
                1.0e-5,
                0.001,
            )
            interface_status_0 = interface_data_0[:2]
            if interface_status_0 != (True, False):
                raise RuntimeError(
                    "Unexpected timestep-0 interface status: {}".format(
                        interface_status_0
                    )
                )
            coefficients_0 = interface_data_0[2:]
            require_close(coefficients_0[0], 100.0, "timestep-0 dp_dq")
            require_close(coefficients_0[1], 0.0, "timestep-0 Hop")

            client.update_state(
                1,
                0,
                0.001,
                1.0e-5,
                0.001,
            )
            client.finalize_timestep(0)

            client.start_timestep(1, 0.002, 0.001)
            if not client.flow_permitted(1, 0.001):
                raise RuntimeError(
                    "The controlled-resistance interface unexpectedly blocked flow."
                )
            if client.boundary_condition_type_changed(1, 0.001):
                raise RuntimeError(
                    "The controlled-resistance interface unexpectedly changed type."
                )

            interface_data_1 = client.compute_interface_data(
                1,
                1,
                0.002,
                1.0e-5,
                0.001,
            )
            coefficients_1 = interface_data_1[2:]
            require_close(coefficients_1[0], 200.0, "timestep-1 dp_dq")
            require_close(coefficients_1[1], 0.0, "timestep-1 Hop")

            client.update_state(
                1,
                1,
                0.002,
                1.0e-5,
                0.001,
            )
            client.finalize_timestep(1)
            client.close()

            output_path = Path(output_directory)
            for filename in (
                "netlistFlows_surface_1.dat",
                "netlistPressures_surface_1.dat",
                "netlistVolumes_surface_1.dat",
            ):
                if not (output_path / filename).is_file():
                    raise RuntimeError(
                        "Worker did not create expected output: {}".format(filename)
                    )

            print("Worker controllers:  {}".format(controller_count))
            print("Interface status:    {}".format(interface_status_0))
            print("dp_dq timestep 0:   {}".format(coefficients_0[0]))
            print("dp_dq timestep 1:   {}".format(coefficients_1[0]))
            print("Production CRIMSON worker client lifecycle: OK")
        except Exception:
            print("Worker transcript:")
            print(client.transcript)
            client.abort()
            raise


def main():
    parser = argparse.ArgumentParser(
        description="Verify the production CRIMSON netlist worker client."
    )
    parser.add_argument(
        "--worker",
        type=Path,
        default=REPOSITORY_ROOT / "ext/build/crimson_netlist_worker",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=REPOSITORY_ROOT / "ext/tests/controllers/netlist_surfaces.xml",
    )
    arguments = parser.parse_args()

    worker = arguments.worker.resolve()
    fixture = arguments.fixture.resolve()
    run_check(worker, fixture)


if __name__ == "__main__":
    main()
