#!/usr/bin/env python3
"""Verify the manager-facing adapter API delegates to the CRIMSON worker."""

from __future__ import annotations

import argparse
import math
import sys
import tempfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from UtilityLib.crimsonNetlistAdapter import CrimsonNetlistAdapter  # noqa: E402


def require_close(actual, expected, name):
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1.0e-12):
        raise RuntimeError(
            "Unexpected {}: {}; expected {}".format(name, actual, expected)
        )


def run_check(worker, fixture):
    """Exercise every adapter method currently used by NetlistBoundaryManager."""
    with tempfile.TemporaryDirectory(
        prefix="starfish adapter protocol "
    ) as temporary_root:
        temporary_root = Path(temporary_root)
        initial_output = temporary_root / "initial output"
        final_output = temporary_root / "final output"
        initial_output.mkdir()
        final_output.mkdir()

        adapter = CrimsonNetlistAdapter(
            netlist_xml=fixture,
            hstep=10,
            alfi=1.0,
            delt=0.001,
            surface_ids=[1],
            output_directory=initial_output,
            worker_executable=worker,
        )

        try:
            adapter.load()

            # Preserve the old adapter behavior that allowed STARFiSh to assign
            # its final SolutionData directory after loading the coupling.
            adapter.set_output_directory(final_output)

            interface_data = adapter.compute_interface_data(
                1,
                0,
                0.001,
                0.001,
                1.0e-5,
            )
            if interface_data[:2] != (True, False):
                raise RuntimeError(
                    "Unexpected interface status: {}".format(interface_data[:2])
                )
            solve_coefficients = interface_data[2:]
            update_coefficients = adapter.compute_update_coefficients(
                1,
                0,
                0.001,
                0.001,
                1.0e-5,
            )

            require_close(solve_coefficients[0], 100.0, "adapter solve dp_dq")
            require_close(solve_coefficients[1], 0.0, "adapter solve Hop")
            require_close(update_coefficients[0], 100.0, "adapter update dp_dq")
            require_close(update_coefficients[1], 0.0, "adapter update Hop")

            adapter.update_state_all_and_finalize(
                0,
                0.001,
                0.001,
                [(1, 0.001, 1.0e-5)],
            )
            adapter.close()

            for filename in (
                "netlistFlows_surface_1.dat",
                "netlistPressures_surface_1.dat",
                "netlistVolumes_surface_1.dat",
            ):
                if not (final_output / filename).is_file():
                    raise RuntimeError(
                        "Adapter did not create expected output: {}".format(filename)
                    )

            print("CrimsonNetlistAdapter worker delegation: OK")
        except Exception:
            adapter.close()
            raise


def main():
    parser = argparse.ArgumentParser(
        description="Verify CrimsonNetlistAdapter worker delegation."
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

    run_check(arguments.worker.resolve(), arguments.fixture.resolve())


if __name__ == "__main__":
    main()
