class NetlistBoundaryManager(object):
    """
    Python-side coordination point for netlist boundary coupling.

    A STARFiSh case owns one global CRIMSON netlist file, conventionally named
    netlist_surfaces.xml. Individual STARFiSh boundaries register by surfaceId;
    the surfaceId maps that 1D boundary to one interface circuit/surface inside
    the shared netlist file.
    """

    def __init__(self):
        """
        Start with no registered STARFiSh boundaries and no loaded CRIMSON
        bridge. The bridge is created lazily the first time a real netlist
        coefficient is requested.
        """
        self.boundaries = {}
        self.boundary_states = {}
        self.pending_states = {}
        self.netlist_file = None
        self.adapter = None
        self._active_timestep = None
        self.output_directory = None

    def set_output_directory(self, output_directory):
        """
        Set where CRIMSON netlist history files should be written.

        STARFiSh run outputs live under results/SolutionData_<number>. The
        CRIMSON netlist writer emits relative file names such as
        netlistPressures_surface_0.dat, so the adapter receives the same
        solution directory and tells the C++ bridge to write from there.
        """
        self.output_directory = output_directory
        if self.adapter is not None:
            self.adapter.set_output_directory(output_directory)

    def register_boundary(
        self,
        surface_id,
        vessel_id=None,
        position=None,
        netlist_file=None,
        flow_sign=1.0,
        rtilde=None,
        s=0.0,
    ):
        """
        Register one STARFiSh boundary against one CRIMSON surface id.

        This is called while STARFiSh reads input.xml. Multiple calls can point
        at the same global netlist_surfaces.xml file. Each call only adds the
        local 1D metadata needed later in the timestep loop:

        surface_id -> vessel_id, boundary position, flow sign, optional fake
        coefficients.
        """
        surface_id = int(surface_id)
        if netlist_file is not None:
            self.set_netlist_file(netlist_file)
        self.boundaries[surface_id] = {
            "vessel_id": vessel_id,
            "position": position,
            "flow_sign": float(flow_sign),
            "rtilde": rtilde,
            "s": s,
        }
        if self.adapter is not None and rtilde is None:
            self.adapter.register_surfaces(self._real_surface_ids())

    def set_netlist_file(self, netlist_file):
        """
        Set the one CRIMSON netlist file for the whole STARFiSh case.

        CRIMSON's netlist file contains all outlet/interface circuits. This
        manager deliberately rejects a second different file because that would
        imply each surface has its own netlist, which is not the CRIMSON model.
        """
        if self.netlist_file is not None and self.netlist_file != netlist_file:
            raise ValueError(
                "Only one global netlist_surfaces.xml file is supported per STARFiSh run. "
                "Existing: {}; requested: {}".format(self.netlist_file, netlist_file)
            )
        self.netlist_file = netlist_file

    def compute_coefficients(self, surface_id, timestep, time, dt, pressure, flow):
        """
        Return the affine netlist law for one surface:

            P = dp_dq * Q + Hop

        During the 1D boundary update, netlistInterface asks this method for
        the current surface's `(dp_dq, Hop)`. If `Rtilde/S` were supplied in
        input.xml, this returns those constants for fake/resistance testing.
        Otherwise it forwards the request to the single CRIMSON adapter.
        """
        surface_id = int(surface_id)
        boundary = self.boundaries.get(surface_id)
        if boundary is None:
            raise KeyError("No netlist boundary registered for surfaceId {}".format(surface_id))
        if boundary["rtilde"] is not None:
            return float(boundary["rtilde"]), float(boundary["s"])
        _, _, dp_dq, hop = self.compute_interface_data(
            surface_id,
            timestep,
            time,
            dt,
            pressure,
            flow,
        )
        return dp_dq, hop

    def compute_interface_data(self, surface_id, timestep, time, dt, pressure, flow):
        """
        Return the full per-surface solve-phase interface payload:

            (flow_permitted, boundary_type_changed, dp_dq, Hop)

        This combines the old status and coefficient requests into one worker
        round-trip for the active coupling path.
        """
        del pressure
        surface_id = int(surface_id)
        boundary = self.boundaries.get(surface_id)
        if boundary is None:
            raise KeyError("No netlist boundary registered for surfaceId {}".format(surface_id))
        if boundary["rtilde"] is not None:
            return True, False, float(boundary["rtilde"]), float(boundary["s"])
        if self._active_timestep != int(timestep):
            self.start_timestep(timestep, time, dt)
        adapter = self._get_adapter(dt)
        return adapter.compute_interface_data(surface_id, timestep, time, dt, flow)

    def compute_update_coefficients(self, surface_id, timestep, time, dt, flow):
        """
        Compute CRIMSON's update-phase coefficients for one real netlist surface.

        The current STARFiSh characteristic solve does not consume these
        coefficients directly, but CRIMSON computes them during its corrector
        phase with `alfi_delt = dt`. Calling this keeps the netlist lifecycle
        closer to the 3D code path.
        """
        surface_id = int(surface_id)
        boundary = self.boundaries.get(surface_id)
        if boundary is None:
            raise KeyError("No netlist boundary registered for surfaceId {}".format(surface_id))
        if boundary["rtilde"] is not None:
            return float(boundary["rtilde"]), float(boundary["s"])
        adapter = self._get_adapter(dt)
        if self._active_timestep != int(timestep):
            self.start_timestep(timestep, time, dt)
        return adapter.compute_update_coefficients(surface_id, timestep, time, dt, flow)

    def flow_permitted(self, surface_id, timestep, time, dt):
        """
        Return whether CRIMSON currently permits interface flow for this surface.

        Fake constant-mode boundaries always permit flow. Real netlist mode
        delegates to CRIMSON after the timestep has been initialized, so closed
        diode cases can switch the 1D interface to a zero-flow condition.
        """
        surface_id = int(surface_id)
        boundary = self.boundaries.get(surface_id)
        if boundary is None:
            raise KeyError("No netlist boundary registered for surfaceId {}".format(surface_id))
        if boundary["rtilde"] is not None:
            return True
        if self._active_timestep != int(timestep):
            self.start_timestep(timestep, time, dt)
        return self._get_adapter(dt).flow_permitted(surface_id, dt)

    def start_timestep(self, timestep, time, dt):
        """
        Start CRIMSON's global netlist timestep once before boundary solves.

        This method now only marks the active timestep on the STARFiSh side.
        The first real coefficient request triggers CRIMSON's actual
        `initialiseAtStartOfTimestep()` call through the worker runtime.
        """
        timestep = int(timestep)
        if self._active_timestep == timestep:
            return None
        self._active_timestep = timestep
        return None

    def record_boundary_state(self, surface_id, timestep, time, dt, pressure, flow):
        """
        Store the final 1D interface state after the characteristic solve.

        This mirrors the CRIMSON flow: each surface first computes its final
        interface pressure/flow, then the global netlist is advanced once at
        the end of the timestep. Therefore this method only records state; it
        does not immediately update/finalize CRIMSON.
        """
        surface_id = int(surface_id)
        state = {
            "timestep": timestep,
            "time": time,
            "dt": dt,
            "pressure": pressure,
            "flow": flow,
        }
        self.boundary_states[surface_id] = state
        boundary = self.boundaries.get(surface_id)
        if boundary is not None and boundary["rtilde"] is None:
            self.pending_states[surface_id] = state

    def finalize_timestep(self, timestep):
        """
        Finalize the global CRIMSON netlist once for a timestep.

        This should be called after the solver has visited all boundary objects
        for the timestep. It pushes every recorded real-netlist surface state
        into CRIMSON, then advances/finalizes the one global netlist. History
        files remain buffered until `close()`.
        """
        if self.pending_states:
            first_state = next(iter(self.pending_states.values()))
            adapter = self._get_adapter(first_state["dt"])
            expected_surfaces = set(self._real_surface_ids())
            pending_surfaces = set(self.pending_states)
            if pending_surfaces != expected_surfaces:
                raise RuntimeError(
                    "Cannot finalize CRIMSON timestep {}: expected states for "
                    "surfaces {}, received {}.".format(
                        timestep,
                        sorted(expected_surfaces),
                        sorted(pending_surfaces),
                    )
                )

            states = []
            for surface_id in sorted(self.pending_states):
                state = self.pending_states[surface_id]
                if int(state["timestep"]) != int(timestep):
                    raise RuntimeError(
                        "Pending state for surface {} belongs to timestep {}, "
                        "not {}.".format(
                            surface_id,
                            state["timestep"],
                            timestep,
                        )
                    )
                states.append(
                    (surface_id, state["pressure"], state["flow"])
                )

            adapter.update_state_all_and_finalize(
                first_state["timestep"],
                first_state["time"],
                first_state["dt"],
                states,
            )
            self.pending_states.clear()
        elif self.adapter is not None:
            self.adapter.finalize_timestep(timestep)
        if self._active_timestep == int(timestep):
            self._active_timestep = None
        return None

    def close(self):
        """
        Flush and stop the simulation-scoped CRIMSON worker, then reset state.

        The default manager is process-wide, so a complete reset is required
        before another case can be loaded in the same Python process.
        """
        adapter = self.adapter
        self.adapter = None
        try:
            if adapter is not None:
                adapter.close()
        finally:
            self.boundaries.clear()
            self.boundary_states.clear()
            self.pending_states.clear()
            self.netlist_file = None
            self._active_timestep = None
            self.output_directory = None

    def _has_real_boundaries(self):
        """
        Return True when any registered boundary needs the CRIMSON adapter.
        """
        for boundary in self.boundaries.values():
            if boundary["rtilde"] is None:
                return True
        return False

    def _get_adapter(self, dt):
        """
        Lazily construct the one Python-to-C++ adapter for this case.

        The manager keeps STARFiSh boundary bookkeeping. The adapter only owns
        the compiled CRIMSON bridge for the global netlist_surfaces.xml file.
        """
        if self.netlist_file is None:
            raise ValueError(
                "Netlist adapter mode requires netlist_surfaces.xml next to input.xml."
            )
        if self.adapter is None:
            from UtilityLib.crimsonNetlistAdapter import CrimsonNetlistAdapter
            self.adapter = CrimsonNetlistAdapter(
                self.netlist_file,
                delt=dt,
                surface_ids=self._real_surface_ids(),
                output_directory=self.output_directory,
            )
            self.adapter.load(dt)
        return self.adapter

    def _real_surface_ids(self):
        """
        Return sorted surface ids that are backed by the CRIMSON netlist.
        """
        return sorted(
            int(surface_id)
            for surface_id, boundary in self.boundaries.items()
            if boundary["rtilde"] is None
        )


_DEFAULT_MANAGER = NetlistBoundaryManager()


def get_default_netlist_manager():
    """
    Return the process-wide manager used by STARFiSh boundary condition objects.
    """
    return _DEFAULT_MANAGER
