#!/usr/bin/env python3
"""End-to-end protocol check for the persistent CRIMSON netlist worker."""

from __future__ import annotations

import argparse
import math
import selectors
import subprocess
import tempfile
from pathlib import Path


RESPONSE_TIMEOUT_SECONDS = 20.0


def quote_worker_argument(value: str) -> str:
    """Quote one value for CrimsonNetlistWorker's command tokenizer."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


class WorkerClient:
    """Small synchronous client used only to verify the worker protocol."""

    def __init__(self, executable: Path) -> None:
        self._transcript: list[str] = []
        self._process = subprocess.Popen(
            [str(executable)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        if self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("Failed to create worker input/output pipes.")

        self._selector = selectors.DefaultSelector()
        self._selector.register(self._process.stdout, selectors.EVENT_READ)
        self.expect("STARFISH_READY")

    @property
    def transcript(self) -> str:
        return "".join(self._transcript)

    def send(self, command: str, expected_prefix: str) -> str:
        if self._process.poll() is not None:
            raise RuntimeError(
                f"Worker exited before command {command!r}.\n{self.transcript}"
            )

        assert self._process.stdin is not None
        self._process.stdin.write(command + "\n")
        self._process.stdin.flush()
        return self.expect(expected_prefix)

    def expect(self, expected_prefix: str) -> str:
        assert self._process.stdout is not None

        while True:
            events = self._selector.select(RESPONSE_TIMEOUT_SECONDS)
            if not events:
                raise RuntimeError(
                    f"Timed out waiting for {expected_prefix!r}.\n"
                    f"Worker transcript:\n{self.transcript}"
                )

            line = self._process.stdout.readline()
            if line == "":
                return_code = self._process.poll()
                raise RuntimeError(
                    f"Worker exited with code {return_code} while waiting for "
                    f"{expected_prefix!r}.\nWorker transcript:\n{self.transcript}"
                )

            self._transcript.append(line)
            response = line.strip()
            if response.startswith(("STARFISH_ERROR", "STARFISH_FATAL")):
                raise RuntimeError(
                    f"Worker reported an error: {response}\n"
                    f"Worker transcript:\n{self.transcript}"
                )
            if response.startswith(expected_prefix):
                return response

    def close(self) -> None:
        if self._process.poll() is not None:
            if self._process.returncode != 0:
                raise RuntimeError(
                    f"Worker exited with code {self._process.returncode}.\n"
                    f"Worker transcript:\n{self.transcript}"
                )
            return

        self.send("QUIT", "STARFISH_OK")
        try:
            return_code = self._process.wait(timeout=RESPONSE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()
            raise RuntimeError(
                f"Worker did not exit after QUIT.\n{self.transcript}"
            )

        if return_code != 0:
            raise RuntimeError(
                f"Worker exited with code {return_code}.\n"
                f"Worker transcript:\n{self.transcript}"
            )

    def abort(self) -> None:
        if self._process.poll() is None:
            self._process.kill()
            self._process.wait()


def parse_coefficients(response: str) -> tuple[float, float]:
    fields = response.split()
    if len(fields) != 3 or fields[0] != "STARFISH_COEFFICIENTS":
        raise RuntimeError(f"Malformed coefficient response: {response}")
    return float(fields[1]), float(fields[2])


def require_close(actual: float, expected: float, name: str) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1.0e-12):
        raise RuntimeError(f"Unexpected {name}: {actual}; expected {expected}")


def run_check(worker: Path, fixture: Path) -> None:
    if not worker.is_file():
        raise RuntimeError(f"Worker executable was not found: {worker}")
    if not fixture.is_file():
        raise RuntimeError(f"Controlled netlist fixture was not found: {fixture}")

    client: WorkerClient | None = None
    with tempfile.TemporaryDirectory(
        prefix="starfish worker protocol "
    ) as output_directory:
        try:
            client = WorkerClient(worker)

            load_response = client.send(
                " ".join(
                    (
                        "LOAD",
                        quote_worker_argument(str(fixture)),
                        quote_worker_argument(output_directory),
                        "10",
                        "1.0",
                        "0.001",
                        "1",
                    )
                ),
                "STARFISH_OK LOAD",
            )
            if load_response != "STARFISH_OK LOAD 1":
                raise RuntimeError(
                    "The worker did not report exactly one controller: "
                    + load_response
                )

            client.send("START 0 0.001", "STARFISH_OK")
            coefficients_0 = parse_coefficients(
                client.send(
                    "COEFFICIENTS 1 0 0.001 1.0e-5",
                    "STARFISH_COEFFICIENTS",
                )
            )
            require_close(coefficients_0[0], 100.0, "timestep-0 dp_dq")
            require_close(coefficients_0[1], 0.0, "timestep-0 Hop")

            client.send("UPDATE 1 0 0.001 1.0e-5", "STARFISH_OK")
            client.send("FINALIZE 0", "STARFISH_OK")

            client.send("START 1 0.002", "STARFISH_OK")
            coefficients_1 = parse_coefficients(
                client.send(
                    "COEFFICIENTS 1 1 0.002 1.0e-5",
                    "STARFISH_COEFFICIENTS",
                )
            )
            require_close(coefficients_1[0], 200.0, "timestep-1 dp_dq")
            require_close(coefficients_1[1], 0.0, "timestep-1 Hop")

            client.send("UPDATE 1 1 0.002 1.0e-5", "STARFISH_OK")
            client.send("FINALIZE 1", "STARFISH_OK")
            client.close()

            output_path = Path(output_directory)
            for filename in (
                "netlistFlows_surface_1.dat",
                "netlistPressures_surface_1.dat",
                "netlistVolumes_surface_1.dat",
            ):
                if not (output_path / filename).is_file():
                    raise RuntimeError(
                        f"Worker did not create expected output: {filename}"
                    )

            print("Worker controllers:  1")
            print(f"dp_dq timestep 0:   {coefficients_0[0]}")
            print(f"dp_dq timestep 1:   {coefficients_1[0]}")
            print("CRIMSON worker protocol lifecycle: OK")
        except Exception:
            if client is not None:
                client.abort()
                print("Worker transcript:")
                print(client.transcript)
            raise


def main() -> None:
    repository_root = Path(__file__).resolve().parents[2]

    parser = argparse.ArgumentParser(
        description="Verify the CRIMSON netlist worker command protocol."
    )
    parser.add_argument(
        "--worker",
        type=Path,
        default=repository_root / "ext/build/crimson_netlist_worker",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=repository_root / "ext/tests/controllers/netlist_surfaces.xml",
    )
    arguments = parser.parse_args()

    run_check(arguments.worker.resolve(), arguments.fixture.resolve())


if __name__ == "__main__":
    main()
