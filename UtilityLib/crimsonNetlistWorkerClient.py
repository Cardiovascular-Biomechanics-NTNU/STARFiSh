"""
Python 3 transport client for the persistent CRIMSON netlist worker.

Why this process boundary exists
--------------------------------
STARFiSh runs inside Python 3, while CRIMSON's existing parameter controllers
embed Python 2.7 through the Python C API. Loading both interpreter ABIs into
the same process is unsafe. The integration therefore runs CRIMSON in a
separate executable:

    STARFiSh Python 3
        -> this client
        -> stdin/stdout text protocol
        -> crimson_netlist_worker
        -> CrimsonNetlistRuntime
        -> NetlistCircuit + ControlSystemsManager + embedded Python 2.7

The worker is persistent. It is started once per STARFiSh simulation and keeps
all circuit histories, diode states, and controller state alive between
timesteps. This client sends only interface data and lifecycle commands.

Ownership boundaries
--------------------
This module owns subprocess communication, response validation, timeouts, and
shutdown. It does not own:

* STARFiSh boundary registration or multi-surface coordination
  (`NetworkLib.netlistManager`);
* characteristic/Riemann-invariant mathematics
  (`NetworkLib.netlistInterface`);
* CRIMSON circuit equations or controllers (`CrimsonNetlistRuntime`);
* selection of when every surface has completed a timestep.

Expected lifecycle
------------------
The intended caller sequence is:

    client.load(...)
    for each timestep:
        for each surface:
            flow_ok, type_changed, dp_dq, hop = client.compute_interface_data(...)
        # STARFiSh solves the unknown characteristic for final P/Q.
        client.update_state_all_and_finalize(...)
    client.close()

The combined finalization call commits CRIMSON histories and runs controllers.
`close()` sends `QUIT`, which writes buffered netlist output and tears down the
isolated runtime. Controller-updated parameters affect coefficients requested
for the following timestep.

Protocol behavior
-----------------
CRIMSON can print diagnostics to stdout. The worker therefore prefixes every
machine-readable response with `STARFISH_`. This client records all lines in a
bounded transcript, ignores unrelated diagnostics while waiting for the
expected prefix, and includes recent output in errors.

Current limitation
------------------
The worker currently uses one fixed `dt` for its lifetime.
"""

from __future__ import annotations

import os
import queue
import subprocess
import threading
from collections import deque
from pathlib import Path


DEFAULT_RESPONSE_TIMEOUT_SECONDS = 20.0
DEFAULT_TRANSCRIPT_LINES = 200
WORKER_ENVIRONMENT_VARIABLE = "STARFISH_CRIMSON_NETLIST_WORKER"


class CrimsonNetlistWorkerError(RuntimeError):
    """
    Error raised for transport, lifecycle, validation, or worker failures.

    Messages generally include the bounded worker transcript so CRIMSON output
    immediately preceding a failure is available without a separate log file.
    """


def _quote_worker_argument(value):
    """
    Quote one value for `CrimsonNetlistWorker`'s line tokenizer.

    Paths can contain spaces. Backslashes and double quotes are escaped to match
    the worker's simple shell-like parser; no shell is involved in execution.
    """
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return '"{}"'.format(escaped)


def _format_number(value):
    """
    Serialize a Python numeric value with enough digits for a C++ double.

    The text protocol is intended to preserve boundary pressures, flows,
    coefficient values, and times without introducing avoidable rounding.
    """
    return format(float(value), ".17g")


def _default_worker_path():
    """
    Resolve the worker executable without coupling callers to the source tree.

    Production/install layouts can set `STARFISH_CRIMSON_NETLIST_WORKER`.
    Development builds fall back to `ext/build/crimson_netlist_worker`.
    """
    configured_path = os.environ.get(WORKER_ENVIRONMENT_VARIABLE)
    if configured_path:
        return Path(configured_path).expanduser().resolve()

    repository_root = Path(__file__).resolve().parents[1]
    return repository_root / "ext" / "build" / "crimson_netlist_worker"


class CrimsonNetlistWorkerClient(object):
    """
    Own and synchronously communicate with one persistent CRIMSON worker.

    One instance represents one simulation-scoped CRIMSON runtime. `load()` can
    be called only once because CRIMSON's XML reader, circuit mapping, and
    controller objects are initialized as one connected stateful system.

    Parameters
    ----------
    worker_executable:
        Optional explicit worker path. If omitted, use
        `STARFISH_CRIMSON_NETLIST_WORKER` or the development build path.
    response_timeout:
        Maximum seconds to wait for each complete protocol response. This is a
        communication timeout, not a CRIMSON numerical convergence tolerance.
    transcript_lines:
        Number of recent stdout lines retained for diagnostics. CRIMSON output
        can be verbose, so this intentionally uses bounded memory.

    Threading
    ---------
    Calls are serialized by a reentrant lock. The protocol is request/response
    and does not support concurrent commands on the same worker. This lock
    prevents accidental interleaving; it does not make CRIMSON itself parallel.
    """

    def __init__(
        self,
        worker_executable=None,
        response_timeout=DEFAULT_RESPONSE_TIMEOUT_SECONDS,
        transcript_lines=DEFAULT_TRANSCRIPT_LINES,
    ):
        self.worker_executable = Path(
            worker_executable if worker_executable is not None else _default_worker_path()
        ).expanduser().resolve()
        self.response_timeout = float(response_timeout)
        if self.response_timeout <= 0.0:
            raise ValueError("Worker response timeout must be positive.")

        self._transcript = deque(maxlen=int(transcript_lines))
        if self._transcript.maxlen is None or self._transcript.maxlen <= 0:
            raise ValueError("Worker transcript length must be positive.")

        # Process and stdout reader are created lazily by start(). Delaying
        # startup lets fake Rtilde/S tests construct higher-level objects
        # without initializing PETSc, MPI, CRIMSON, or Python 2.
        self._process = None
        self._stdout_queue = None
        self._stdout_reader = None
        self._stdout_eof = object()

        # The protocol is strictly synchronous. Guard a full write/read exchange
        # so two callers cannot mix commands and consume each other's responses.
        self._lock = threading.RLock()

        # These values mirror the immutable simulation-scoped configuration in
        # CrimsonNetlistRuntime and support local validation before IPC.
        self._loaded = False
        self._dt = None
        self._surface_ids = ()

    @property
    def loaded(self):
        """Whether the worker has successfully completed its `LOAD` command."""
        return self._loaded

    @property
    def surface_ids(self):
        """Sorted immutable tuple of STARFiSh surface IDs loaded by CRIMSON."""
        return self._surface_ids

    @property
    def transcript(self):
        """
        Return recent worker output, including non-protocol CRIMSON diagnostics.

        Only the most recent `transcript_lines` lines are retained. Protocol
        consumers should use method return values rather than parse this text.
        """
        return "".join(self._transcript)

    def start(self):
        """
        Start the worker executable and wait for `STARFISH_READY`.

        Startup initializes PETSc/MPI and the embedded Python 2 interpreter in
        the child process. Calling `start()` again while the worker is alive is
        harmless and returns this client. A previously exited worker is not
        silently restarted because its CRIMSON state has been lost.
        """
        with self._lock:
            if self._process is not None:
                if self._process.poll() is None:
                    return self
                raise CrimsonNetlistWorkerError(
                    "The CRIMSON worker has already exited.\n{}".format(
                        self._diagnostic_transcript()
                    )
                )

            if not self.worker_executable.is_file():
                raise CrimsonNetlistWorkerError(
                    "CRIMSON netlist worker was not found: {}".format(
                        self.worker_executable
                    )
                )
            if not os.access(str(self.worker_executable), os.X_OK):
                raise CrimsonNetlistWorkerError(
                    "CRIMSON netlist worker is not executable: {}".format(
                        self.worker_executable
                    )
                )

            # stderr is merged into stdout so one ordered transcript contains
            # both CRIMSON diagnostics and machine-readable protocol responses.
            # `shell=False` (the default) avoids shell parsing and injection.
            self._process = subprocess.Popen(
                [str(self.worker_executable)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if self._process.stdin is None or self._process.stdout is None:
                self.abort()
                raise CrimsonNetlistWorkerError(
                    "Failed to create CRIMSON worker input/output pipes."
                )

            # TextIOWrapper can read several pipe lines into its own buffer at
            # once. Waiting on an OS-level selector before every readline()
            # therefore misses lines already buffered in Python. Keep one
            # reader thread blocked in readline() and deliver complete lines
            # through a queue so diagnostics and the following protocol reply
            # cannot produce a false timeout.
            self._stdout_queue = queue.Queue()
            self._stdout_reader = threading.Thread(
                target=self._read_stdout,
                name="crimson-netlist-worker-stdout",
                daemon=True,
            )
            self._stdout_reader.start()
            self._expect("STARFISH_READY")
            return self

    def load(
        self,
        netlist_xml,
        output_directory,
        hstep,
        alfi,
        dt,
        surface_ids,
        starting_timestep=0,
        restart_interval=1000,
        master_control_script_present=False,
    ):
        """
        Create the worker's one simulation-scoped `CrimsonNetlistRuntime`.

        Parameters map directly to the worker's extended `LOAD` command:

        * `netlist_xml`: global `netlist_surfaces.xml` containing all circuits;
        * `output_directory`: destination for CRIMSON P/Q/volume histories, or
          `None` to retain CRIMSON's current-directory behavior;
        * `hstep`, `alfi`, `dt`: CRIMSON integration constructor values;
        * `surface_ids`: STARFiSh-facing IDs whose sorted order maps to XML
          circuit order;
        * restart/master-controller fields: passed unchanged to CRIMSON.

        Returns
        -------
        int
            Number of Python/native controllers registered by CRIMSON.

        Notes
        -----
        All surfaces must be known before this call. The current worker owns one
        fixed circuit system and does not support registering another surface
        after `LOAD`.
        """
        with self._lock:
            if self._loaded:
                raise CrimsonNetlistWorkerError(
                    "The CRIMSON worker runtime has already been loaded."
                )

            netlist_xml = Path(netlist_xml).expanduser().resolve()
            if not netlist_xml.is_file():
                raise CrimsonNetlistWorkerError(
                    "CRIMSON netlist XML was not found: {}".format(netlist_xml)
                )

            if output_directory is None:
                output_value = "-"
            else:
                output_directory = Path(output_directory).expanduser().resolve()
                if not output_directory.is_dir():
                    raise CrimsonNetlistWorkerError(
                        "CRIMSON output directory was not found: {}".format(
                            output_directory
                        )
                    )
                output_value = str(output_directory)

            # Sorting reproduces CrimsonNetlistRuntime's deterministic mapping:
            # sorted STARFiSh surface ID position -> CRIMSON XML circuit index.
            normalized_surface_ids = tuple(
                sorted(set(int(surface_id) for surface_id in surface_ids))
            )
            if not normalized_surface_ids:
                raise CrimsonNetlistWorkerError(
                    "At least one CRIMSON netlist surface ID is required."
                )

            resolved_dt = float(dt)
            if resolved_dt <= 0.0:
                raise CrimsonNetlistWorkerError(
                    "CRIMSON worker timestep dt must be positive."
                )

            # start() is intentionally lazy and idempotent; load() remains the
            # normal first public call for production use.
            self.start()
            response = self._send(
                " ".join(
                    (
                        "LOAD",
                        _quote_worker_argument(netlist_xml),
                        _quote_worker_argument(output_value),
                        str(int(hstep)),
                        _format_number(alfi),
                        _format_number(resolved_dt),
                        str(int(starting_timestep)),
                        str(int(restart_interval)),
                        "1" if master_control_script_present else "0",
                        ",".join(str(surface_id) for surface_id in normalized_surface_ids),
                    )
                ),
                "STARFISH_OK LOAD",
            )

            fields = response.split()
            if len(fields) != 3:
                raise CrimsonNetlistWorkerError(
                    "Malformed LOAD response: {}".format(response)
                )

            try:
                controller_count = int(fields[2])
            except ValueError as error:
                raise CrimsonNetlistWorkerError(
                    "Malformed controller count in LOAD response: {}".format(response)
                ) from error

            self._loaded = True
            self._dt = resolved_dt
            self._surface_ids = normalized_surface_ids
            return controller_count

    def start_timestep(self, timestep, time, dt=None):
        """
        Run CRIMSON's once-per-global-timestep initialization phase.

        This calls `NetlistCircuit::initialiseAtStartOfTimestep()` for every
        loaded surface. Higher-level coordination should call it once before
        requesting coefficients for any boundary at the timestep.
        """
        with self._lock:
            self._require_loaded()
            self._require_matching_dt(dt)
            self._send(
                "START {} {}".format(int(timestep), _format_number(time)),
                "STARFISH_OK",
            )

    def start_timestep_and_status(self, timestep, time, surface_ids, dt=None):
        with self._lock:
            self._require_loaded()
            self._require_matching_dt(dt)
            normalized_ids = tuple(int(surface_id) for surface_id in surface_ids)
            if not normalized_ids:
                raise CrimsonNetlistWorkerError(
                    "START_AND_STATUS requires at least one surface."
                )
            for surface_id in normalized_ids:
                self._require_surface(surface_id)

            fields = self._send(
                "START_AND_STATUS {} {} {} {}".format(
                    int(timestep),
                    _format_number(time),
                    len(normalized_ids),
                    " ".join(str(surface_id) for surface_id in normalized_ids),
                ),
                "STARFISH_START_STATUS",
            ).split()
            if len(fields) != 1 + 2 * len(normalized_ids):
                raise CrimsonNetlistWorkerError(
                    "Malformed START_AND_STATUS response: {}".format(
                        " ".join(fields)
                    )
                )

            statuses = {}
            for index, surface_id in enumerate(normalized_ids):
                statuses[surface_id] = (
                    self._parse_protocol_bool(
                        fields[1 + 2 * index],
                        "flow-permitted flag",
                    ),
                    self._parse_protocol_bool(
                        fields[2 + 2 * index],
                        "boundary-type-changed flag",
                    ),
                )
            return statuses

    def update_state_all_and_finalize(self, timestep, time, surface_states, dt=None):
        with self._lock:
            self._require_loaded()
            self._require_matching_dt(dt)
            normalized_states = tuple(
                (int(surface_id), float(pressure), float(flow))
                for surface_id, pressure, flow in surface_states
            )
            if not normalized_states:
                raise CrimsonNetlistWorkerError(
                    "UPDATE_ALL_AND_FINALIZE requires at least one surface."
                )

            arguments = []
            for surface_id, pressure, flow in normalized_states:
                self._require_surface(surface_id)
                arguments.extend(
                    (
                        str(surface_id),
                        _format_number(pressure),
                        _format_number(flow),
                    )
                )

            self._send(
                "UPDATE_ALL_AND_FINALIZE {} {} {} {}".format(
                    int(timestep),
                    _format_number(time),
                    len(normalized_states),
                    " ".join(arguments),
                ),
                "STARFISH_OK",
            )

    def compute_coefficients(self, surface_id, timestep, time, flow, dt=None):
        """
        Return CRIMSON's affine interface law `(dp_dq, Hop)` for one surface.

        The supplied flow follows the sign convention established by the
        STARFiSh netlist interface/manager. CRIMSON returns:

            P_interface = dp_dq * Q_interface + Hop

        STARFiSh then combines this equation with the known characteristic to
        solve the unknown incoming characteristic and final interface P/Q.
        """
        with self._lock:
            self._require_surface(surface_id)
            self._require_matching_dt(dt)
            response = self._send(
                "COEFFICIENTS {} {} {} {}".format(
                    int(surface_id),
                    int(timestep),
                    _format_number(time),
                    _format_number(flow),
                ),
                "STARFISH_COEFFICIENTS",
            )
            fields = response.split()
            if len(fields) != 3:
                raise CrimsonNetlistWorkerError(
                    "Malformed COEFFICIENTS response: {}".format(response)
                )
            try:
                return float(fields[1]), float(fields[2])
            except ValueError as error:
                raise CrimsonNetlistWorkerError(
                    "Non-numeric COEFFICIENTS response: {}".format(response)
                ) from error

    def compute_interface_data(self, surface_id, timestep, time, flow, dt=None):
        """
        Return flow/type flags and solve-phase coefficients in one response.

        The returned tuple is:

            (flow_permitted, boundary_condition_type_changed, dp_dq, Hop)

        When flow is not permitted, the coefficient entries may be NaN because
        STARFiSh will switch to its prescribed-flow treatment instead.
        """
        with self._lock:
            self._require_surface(surface_id)
            self._require_matching_dt(dt)
            response = self._send(
                "INTERFACE_DATA {} {} {} {}".format(
                    int(surface_id),
                    int(timestep),
                    _format_number(time),
                    _format_number(flow),
                ),
                "STARFISH_INTERFACE_DATA",
            )
            fields = response.split()
            if len(fields) != 5:
                raise CrimsonNetlistWorkerError(
                    "Malformed INTERFACE_DATA response: {}".format(response)
                )
            try:
                return (
                    self._parse_protocol_bool(fields[1], "flow-permitted flag"),
                    self._parse_protocol_bool(
                        fields[2],
                        "boundary-type-changed flag",
                    ),
                    float(fields[3]),
                    float(fields[4]),
                )
            except ValueError as error:
                raise CrimsonNetlistWorkerError(
                    "Non-numeric INTERFACE_DATA response: {}".format(response)
                ) from error

    def compute_update_coefficients(
        self,
        surface_id,
        timestep,
        time,
        flow,
        dt=None,
    ):
        """
        Return CRIMSON's update/corrector-phase `(dp_dq, Hop)` coefficients.

        CRIMSON's solve phase forms differential-component terms with
        `alfi * dt`, while its update phase intentionally calls the same
        coefficient machinery with `dt`. STARFiSh's manager currently requests
        this second coefficient set before pushing final interface state.
        """
        with self._lock:
            self._require_surface(surface_id)
            self._require_matching_dt(dt)
            response = self._send(
                "UPDATE_COEFFICIENTS {} {} {} {}".format(
                    int(surface_id),
                    int(timestep),
                    _format_number(time),
                    _format_number(flow),
                ),
                "STARFISH_UPDATE_COEFFICIENTS",
            )
            fields = response.split()
            if len(fields) != 3:
                raise CrimsonNetlistWorkerError(
                    "Malformed UPDATE_COEFFICIENTS response: {}".format(response)
                )
            try:
                return float(fields[1]), float(fields[2])
            except ValueError as error:
                raise CrimsonNetlistWorkerError(
                    "Non-numeric UPDATE_COEFFICIENTS response: {}".format(response)
                ) from error

    def interface_status(self, surface_id, dt=None):
        """
        Return `(flow_permitted, boundary_condition_type_changed)`.

        `flow_permitted` is false when a non-leaky closed diode blocks the
        CRIMSON interface and STARFiSh must use a zero-flow boundary treatment
        instead of the affine Robin law.

        `boundary_condition_type_changed` reports CRIMSON's transition flag so
        STARFiSh can reset or reinterpret interface state when the circuit
        switches between pressure/Robin and blocked-flow behavior.

        Both flags are fetched in one protocol exchange because they describe
        the same surface state and are commonly consumed together.
        """
        with self._lock:
            self._require_surface(surface_id)
            self._require_matching_dt(dt)
            response = self._send(
                "INTERFACE_STATUS {}".format(int(surface_id)),
                "STARFISH_INTERFACE_STATUS",
            )
            fields = response.split()
            if len(fields) != 3:
                raise CrimsonNetlistWorkerError(
                    "Malformed INTERFACE_STATUS response: {}".format(response)
                )

            try:
                flow_permitted = self._parse_protocol_bool(
                    fields[1],
                    "flow-permitted flag",
                )
                type_changed = self._parse_protocol_bool(
                    fields[2],
                    "boundary-type-changed flag",
                )
            except ValueError as error:
                raise CrimsonNetlistWorkerError(
                    "Non-boolean INTERFACE_STATUS response: {}".format(response)
                ) from error

            return flow_permitted, type_changed

    def flow_permitted(self, surface_id, dt=None):
        """Return whether CRIMSON currently permits flow at this interface."""
        return self.interface_status(surface_id, dt)[0]

    def boundary_condition_type_changed(self, surface_id, dt=None):
        """Return CRIMSON's interface boundary-mode transition flag."""
        return self.interface_status(surface_id, dt)[1]

    def set_output_directory(self, output_directory):
        """
        Change where subsequent CRIMSON history files are written.

        The directory must already exist. This method is mainly present to
        preserve `CrimsonNetlistAdapter.set_output_directory()` behavior when
        STARFiSh assigns its `SolutionData_<number>` directory after creating
        higher-level coupling objects.
        """
        with self._lock:
            self._require_loaded()
            output_directory = Path(output_directory).expanduser().resolve()
            if not output_directory.is_dir():
                raise CrimsonNetlistWorkerError(
                    "CRIMSON output directory was not found: {}".format(
                        output_directory
                    )
                )
            self._send(
                "SET_OUTPUT_DIRECTORY {}".format(
                    _quote_worker_argument(output_directory)
                ),
                "STARFISH_OK",
            )

    def update_state(self, surface_id, timestep, pressure, flow, dt=None):
        """
        Push one surface's final STARFiSh pressure and flow into CRIMSON.

        Call this only after the characteristic solve has produced final P/Q.
        For multiple surfaces, every surface must be updated before the single
        global `finalize_timestep()` call.
        """
        with self._lock:
            self._require_surface(surface_id)
            self._require_matching_dt(dt)
            self._send(
                "UPDATE {} {} {} {}".format(
                    int(surface_id),
                    int(timestep),
                    _format_number(pressure),
                    _format_number(flow),
                ),
                "STARFISH_OK",
            )

    def finalize_timestep(self, timestep):
        """
        Finalize all circuits once after every surface has been updated.

        CRIMSON commits pressure/flow/volume histories and runs native/Python
        controllers. Buffered output files are written by `close()` through
        the worker's `QUIT` handler. Parameter changes made by controllers
        affect coefficient calculations in the next timestep.
        """
        with self._lock:
            self._require_loaded()
            self._send("FINALIZE {}".format(int(timestep)), "STARFISH_OK")

    def close(self):
        """
        Send `QUIT`, wait for ordered CRIMSON teardown, and close local pipes.

        The child destroys runtime/controller objects before finalizing the XML
        reader, Python 2, and PETSc/MPI. `close()` is idempotent after resources
        have been released. Use `abort()` only when graceful communication is no
        longer possible.
        """
        with self._lock:
            if self._process is None:
                return

            process = self._process
            try:
                if process.poll() is None:
                    self._send("QUIT", "STARFISH_OK")
                    try:
                        return_code = process.wait(timeout=self.response_timeout)
                    except subprocess.TimeoutExpired as error:
                        process.kill()
                        process.wait()
                        raise CrimsonNetlistWorkerError(
                            "CRIMSON worker did not exit after QUIT.\n{}".format(
                                self._diagnostic_transcript()
                            )
                        ) from error
                    if return_code != 0:
                        raise CrimsonNetlistWorkerError(
                            "CRIMSON worker exited with code {}.\n{}".format(
                                return_code,
                                self._diagnostic_transcript(),
                            )
                        )
            finally:
                self._release_process_resources()

    def abort(self):
        """
        Kill the worker immediately and release local communication resources.

        This bypasses CRIMSON's graceful history/controller/Python teardown and
        is intended only for exception cleanup, hangs, or broken pipes.
        """
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                self._process.kill()
                self._process.wait()
            self._release_process_resources()

    def __enter__(self):
        """Start the worker when entering a context-manager scope."""
        return self.start()

    def __exit__(self, exception_type, exception, traceback):
        """Close normally, or abort when the managed scope raises an error."""
        if exception_type is None:
            self.close()
        else:
            self.abort()
        return False

    def _send(self, command, expected_prefix):
        """
        Write one complete command and synchronously wait for its response.

        The lock is held by every public caller, so this method never has more
        than one outstanding request on a worker.
        """
        process = self._require_running()
        try:
            process.stdin.write(command + "\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            raise CrimsonNetlistWorkerError(
                "Failed to send command to CRIMSON worker: {!r}\n{}".format(
                    command,
                    self._diagnostic_transcript(),
                )
            ) from error
        return self._expect(expected_prefix)

    def _expect(self, expected_prefix):
        """
        Read output until the expected machine-readable prefix appears.

        CRIMSON diagnostic lines are retained but otherwise ignored. Explicit
        `STARFISH_ERROR` and `STARFISH_FATAL` responses fail immediately.
        """
        process = self._require_running()
        while True:
            try:
                line = self._stdout_queue.get(timeout=self.response_timeout)
            except queue.Empty:
                raise CrimsonNetlistWorkerError(
                    "Timed out waiting for {!r}.\n{}".format(
                        expected_prefix,
                        self._diagnostic_transcript(),
                    )
                )

            if line is self._stdout_eof:
                raise CrimsonNetlistWorkerError(
                    "CRIMSON worker exited with code {} while waiting for {!r}.\n{}".format(
                        process.poll(),
                        expected_prefix,
                        self._diagnostic_transcript(),
                    )
                )

            # Record every line before interpreting it so failures include the
            # exact CRIMSON/protocol context that led to the exception.
            self._transcript.append(line)
            response = line.strip()
            if response.startswith(("STARFISH_ERROR", "STARFISH_FATAL")):
                raise CrimsonNetlistWorkerError(
                    "CRIMSON worker reported: {}\n{}".format(
                        response,
                        self._diagnostic_transcript(),
                    )
                )
            if response.startswith(expected_prefix):
                return response

    def _read_stdout(self):
        """Forward worker output to the timeout-aware response queue."""
        process = self._process
        try:
            if process is None or process.stdout is None:
                return
            while True:
                line = process.stdout.readline()
                if line == "":
                    break
                self._stdout_queue.put(line)
        finally:
            if self._stdout_queue is not None:
                self._stdout_queue.put(self._stdout_eof)


    def _require_running(self):
        """Return the live process or raise with recent diagnostic output."""
        if self._process is None:
            raise CrimsonNetlistWorkerError(
                "The CRIMSON worker process has not been started."
            )
        if self._process.poll() is not None:
            raise CrimsonNetlistWorkerError(
                "The CRIMSON worker exited with code {}.\n{}".format(
                    self._process.returncode,
                    self._diagnostic_transcript(),
                )
            )
        return self._process

    def _require_loaded(self):
        """Require both a live process and a successfully loaded runtime."""
        self._require_running()
        if not self._loaded:
            raise CrimsonNetlistWorkerError(
                "The CRIMSON worker runtime has not been loaded."
            )

    def _require_surface(self, surface_id):
        """Reject calls for surfaces outside the immutable loaded mapping."""
        self._require_loaded()
        surface_id = int(surface_id)
        if surface_id not in self._surface_ids:
            raise CrimsonNetlistWorkerError(
                "Surface {} is not registered with the CRIMSON worker.".format(
                    surface_id
                )
            )

    def _require_matching_dt(self, dt):
        """
        Enforce the current fixed-timestep CRIMSON runtime contract.

        CRIMSON constructs differential component matrices using the `dt`
        supplied at `LOAD`. STARFiSh may pass `dt` with every method call for API
        compatibility, but it must remain exactly the loaded value for now.
        """
        if dt is None:
            return
        if float(dt) != self._dt:
            raise CrimsonNetlistWorkerError(
                "CRIMSON worker uses fixed dt={}; received dt={}.".format(
                    self._dt,
                    float(dt),
                )
            )

    @staticmethod
    def _parse_protocol_bool(value, name):
        """Parse the worker's strict numeric boolean representation."""
        if value == "1":
            return True
        if value == "0":
            return False
        raise ValueError("Invalid {}: {}".format(name, value))

    def _diagnostic_transcript(self):
        """Format the bounded worker transcript for exception messages."""
        if not self._transcript:
            return "Worker transcript is empty."
        return "Recent worker transcript:\n{}".format(self.transcript)

    def _release_process_resources(self):
        """
        Close local pipe objects and reset client-side lifecycle state.

        This method does not terminate a live child; callers must first complete
        `QUIT` or kill the process.
        """
        if self._process is not None:
            if self._process.stdin is not None:
                self._process.stdin.close()
            if self._stdout_reader is not None:
                self._stdout_reader.join(timeout=self.response_timeout)
            if self._process.stdout is not None:
                self._process.stdout.close()
        self._stdout_queue = None
        self._stdout_reader = None
        self._process = None
        self._loaded = False
        self._dt = None
        self._surface_ids = ()
