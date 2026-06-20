"""STARFiSh-facing adapter for the isolated CRIMSON netlist worker."""

import atexit
import os

from UtilityLib.crimsonNetlistWorkerClient import CrimsonNetlistWorkerClient


# CRIMSON uses this interval for Python-controller restart pickles. STARFiSh
# does not yet expose restart support, so avoid periodic pickle I/O while still
# keeping the positive interval required by ControlSystemsManager.
DISABLED_RESTART_INTERVAL = 1000000000


class CrimsonNetlistAdapter(object):
    """
    Preserve STARFiSh's netlist adapter API while using a worker subprocess.

    `NetlistBoundaryManager` owns surface coordination and decides when a
    global timestep starts or finishes. This adapter translates that existing
    API into calls on `CrimsonNetlistWorkerClient`.

    The CRIMSON worker owns all circuit histories and Python 2 controller state.
    It remains alive from `load()` until `close()` or Python process exit.
    """

    def __init__(
        self,
        netlist_xml,
        hstep=1,
        alfi=1.0,
        delt=None,
        surface_ids=None,
        output_directory=None,
        worker_executable=None,
    ):
        """
        Store simulation-scoped CRIMSON configuration without starting CRIMSON.

        The worker is loaded lazily so fake `Rtilde/S` cases never initialize
        PETSc, MPI, CRIMSON, or Python 2.
        """
        self.netlist_xml = os.path.abspath(netlist_xml)
        self.hstep = int(hstep)
        self.alfi = float(alfi)
        self.delt = None if delt is None else float(delt)
        self.surface_ids = sorted(
            set(int(surface_id) for surface_id in (surface_ids or []))
        )
        self.output_directory = (
            os.path.abspath(output_directory)
            if output_directory is not None
            else None
        )
        self.worker_executable = worker_executable
        self._client = None

        # STARFiSh currently has no explicit simulation-wide adapter teardown.
        # Register a final safety net so successful runs do not leave the
        # persistent worker alive when the Python process exits.
        atexit.register(self.close)

    def set_output_directory(self, output_directory):
        """
        Set where CRIMSON pressure, flow, and volume histories are written.

        The normal solver calls this before lazy loading. If it is called after
        loading, forward the change to the existing runtime.
        """
        self.output_directory = (
            os.path.abspath(output_directory)
            if output_directory is not None
            else None
        )
        if self._client is not None and self.output_directory is not None:
            self._client.set_output_directory(self.output_directory)

    def register_surfaces(self, surface_ids):
        """
        Add STARFiSh-facing surface IDs before the worker runtime is loaded.

        CRIMSON maps sorted surface IDs to XML circuit order while loading one
        connected circuit system. A loaded runtime cannot safely add another
        surface because that would change the established mapping and controller
        pointers.
        """
        new_ids = sorted(set(int(surface_id) for surface_id in surface_ids))
        merged_ids = sorted(set(self.surface_ids).union(new_ids))
        if merged_ids == self.surface_ids:
            return None
        if self._client is not None:
            raise RuntimeError(
                "Cannot register new CRIMSON netlist surfaces after the worker "
                "runtime has been loaded."
            )
        self.surface_ids = merged_ids
        return None

    def load(self, dt=None):
        """
        Start the isolated worker and load the global netlist circuit system.

        Returns this adapter for compatibility with the previous in-process
        nanobind implementation.
        """
        if self._client is not None:
            return self

        resolved_dt = self._resolve_dt(dt)
        if not self.surface_ids:
            raise ValueError(
                "At least one surface ID must be registered before loading "
                "the CRIMSON netlist worker."
            )

        client = CrimsonNetlistWorkerClient(
            worker_executable=self.worker_executable
        )
        try:
            client.load(
                netlist_xml=self.netlist_xml,
                output_directory=self.output_directory,
                hstep=self.hstep,
                alfi=self.alfi,
                dt=resolved_dt,
                surface_ids=self.surface_ids,
                restart_interval=DISABLED_RESTART_INTERVAL,
            )
        except Exception:
            client.abort()
            raise

        self._client = client
        self.delt = resolved_dt
        return self


    def start_timestep_and_status(self, timestep, time, dt):
        client = self._ensure_client(dt)
        return client.start_timestep_and_status(
            int(timestep), float(time), self.surface_ids, float(dt)
        )

    def compute_interface_data(
        self,
        surface_id,
        timestep,
        time,
        dt,
        flow,
    ):
        """
        Return `(flow_permitted, type_changed, dp_dq, Hop)` for one surface.
        """
        client = self._ensure_client(dt)
        return client.compute_interface_data(
            int(surface_id),
            int(timestep),
            float(time),
            float(flow),
            float(dt),
        )

    def update_state_all_and_finalize(self, timestep, time, dt, surface_states):
        client = self._ensure_client(dt)
        client.update_state_all_and_finalize(
            int(timestep), float(time), surface_states, float(dt)
        )

    def compute_implicit_coefficients(
        self,
        surface_id,
        timestep,
        time,
        dt,
        flow,
    ):
        """
        Return `(dp_dq, Hop)` for the solve-phase affine interface law.

            P_interface = dp_dq * Q_interface + Hop
        """
        client = self._ensure_client(dt)
        return client.compute_coefficients(
            int(surface_id),
            int(timestep),
            float(time),
            float(flow),
            float(dt),
        )

    def compute_update_coefficients(
        self,
        surface_id,
        timestep,
        time,
        dt,
        flow,
    ):
        """
        Return CRIMSON's update/corrector-phase coefficient pair.

        This preserves CRIMSON's distinct call using `alfi_delt = dt`.
        """
        client = self._ensure_client(dt)
        return client.compute_update_coefficients(
            int(surface_id),
            int(timestep),
            float(time),
            float(flow),
            float(dt),
        )

    def flow_permitted(self, surface_id, dt=None):
        """Return whether the current CRIMSON interface permits flow."""
        client = self._ensure_client(dt)
        return bool(client.flow_permitted(int(surface_id), dt))

    def boundary_condition_type_changed(self, surface_id, dt=None):
        """Return CRIMSON's interface boundary-mode transition flag."""
        client = self._ensure_client(dt)
        return bool(
            client.boundary_condition_type_changed(int(surface_id), dt)
        )

    def start_timestep(self, timestep, time, dt):
        """
        Run CRIMSON's once-per-global-timestep initialization phase.
        """
        client = self._ensure_client(dt)
        client.start_timestep(
            int(timestep),
            float(time),
            float(dt),
        )

    def update_state(
        self,
        surface_id,
        timestep,
        time,
        dt,
        pressure,
        flow,
    ):
        """
        Push final STARFiSh interface pressure/flow into CRIMSON.

        `time` remains in this compatibility signature although CRIMSON's
        `updateLPN()` call only needs surface, timestep, pressure, and flow.
        """
        del time
        client = self._ensure_client(dt)
        client.update_state(
            int(surface_id),
            int(timestep),
            float(pressure),
            float(flow),
            float(dt),
        )

    def finalize_timestep(self, timestep):
        """
        Commit histories and execute CRIMSON controllers for one timestep.

        History files are buffered and written during `close()`.
        """
        if self._client is not None:
            self._client.finalize_timestep(int(timestep))

    def close(self):
        """
        Gracefully terminate the persistent worker.

        This method is idempotent and can be called explicitly by future
        simulation-level cleanup code in addition to the registered atexit hook.
        """
        if self._client is None:
            return
        client = self._client
        self._client = None
        client.close()

    def _ensure_client(self, dt):
        """Load the worker lazily and return its production client."""
        if self._client is None:
            self.load(dt)
        return self._client

    def _resolve_dt(self, dt):
        """Resolve and enforce the current fixed-timestep runtime contract."""
        if dt is not None:
            resolved_dt = float(dt)
            if self.delt is not None and resolved_dt != float(self.delt):
                raise ValueError(
                    "CRIMSON netlist adapter uses fixed dt={}; received dt={}."
                    .format(self.delt, resolved_dt)
                )
            return resolved_dt
        if self.delt is None:
            raise ValueError(
                "A timestep dt is required before loading the CRIMSON netlist "
                "worker."
            )
        return float(self.delt)
