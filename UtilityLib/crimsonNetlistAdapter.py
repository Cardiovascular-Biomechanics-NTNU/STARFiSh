import os
import sys


class CrimsonNetlistAdapter(object):
    """
    Thin Python wrapper around the compiled CRIMSON bridge.

    NetlistBoundaryManager owns the STARFiSh-side coupling state and decides
    which surface is being queried. This adapter only loads one global
    netlist_surfaces.xml file and forwards coefficient/state calls to
    ext/StarfishBridge.cpp through the nanobind module.
    """

    def __init__(self, netlist_xml, hstep=1, alfi=1.0, delt=None, surface_ids=None):
        """
        Store the one CRIMSON netlist file and bridge time-integration settings.

        No STARFiSh vessel or boundary metadata belongs here. Surface selection
        is passed through each method call from NetlistBoundaryManager.
        """
        self.netlist_xml = os.path.abspath(netlist_xml)
        self.hstep = hstep
        self.alfi = alfi
        self.delt = delt
        self.surface_ids = sorted(set(int(surface_id) for surface_id in (surface_ids or [])))
        self._bridge = None

    def load(self, dt=None):
        """
        Import the nanobind module, construct `CrimsonBridge`, and load XML.

        CRIMSON's XML reader still has a current-directory assumption for
        netlist_surfaces.xml, so loading temporarily runs from the XML
        directory. After this method returns, Python code talks to
        ext/StarfishBridge.cpp through `self._bridge`.
        """
        dt = self._resolve_dt(dt)
        module = self._import_bridge_module()
        self._bridge = module.CrimsonBridge(self.hstep, self.alfi, dt)
        previous_cwd = os.getcwd()
        xml_dir = os.path.dirname(self.netlist_xml)
        try:
            if xml_dir:
                os.chdir(xml_dir)
            if self.surface_ids:
                self._bridge.load(self.netlist_xml, self.surface_ids)
            else:
                self._bridge.load(self.netlist_xml)
        finally:
            os.chdir(previous_cwd)
        return self

    def compute_implicit_coefficients(self, surface_id, timestep, time, dt, flow):
        """
        Ask CRIMSON for the current surface's Robin coefficients.

        Expected output is `(dp_dq, Hop)` for:

            P_interface = dp_dq * Q_interface + Hop

        The C++ bridge uses `surface_id` to select the corresponding CRIMSON
        `NetlistCircuit`.
        """
        bridge = self._ensure_bridge(dt)
        return bridge.compute_implicit_coefficients(
            int(surface_id),
            int(timestep),
            float(time),
            float(dt),
            float(flow),
        )

    def compute_update_coefficients(self, surface_id, timestep, time, dt, flow):
        """
        Ask CRIMSON for the update-phase coefficients.

        This mirrors CRIMSON's `computeImplicitCoeff_update`, which calls the
        netlist coefficient computation with `alfi_delt = delt`.
        """
        bridge = self._ensure_bridge(dt)
        return bridge.compute_update_coefficients(
            int(surface_id),
            int(timestep),
            float(time),
            float(dt),
            float(flow),
        )

    def flow_permitted(self, surface_id, dt=None):
        """
        Return CRIMSON's current diode/interface flow-permission state.
        """
        bridge = self._ensure_bridge(dt)
        return bool(bridge.flow_permitted(int(surface_id)))

    def boundary_condition_type_changed(self, surface_id, dt=None):
        """
        Return whether CRIMSON reports a boundary-mode change for this surface.
        """
        bridge = self._ensure_bridge(dt)
        return bool(bridge.boundary_condition_type_changed(int(surface_id)))

    def start_timestep(self, timestep, time, dt):
        """
        Run CRIMSON's per-timestep netlist preparation phase.

        This mirrors `initialiseAtStartOfTimestep()` in CRIMSON. It must happen
        once before coefficients are requested for a timestep so diode switching,
        controller updates, and per-step bookkeeping are applied consistently.
        """
        bridge = self._ensure_bridge(dt)
        bridge.start_timestep(int(timestep), float(time), float(dt))

    def update_state(self, surface_id, timestep, time, dt, pressure, flow):
        """
        Push final STARFiSh interface pressure/flow into CRIMSON.

        This is called after netlistInterface solves the unknown characteristic.
        For a full multi-surface bridge, CRIMSON should receive final states for
        all surfaces before finalizing the timestep.
        """
        bridge = self._ensure_bridge(dt)
        bridge.update_state(
            int(surface_id),
            int(timestep),
            float(time),
            float(dt),
            float(pressure),
            float(flow),
        )

    def finalize_timestep(self, timestep):
        """
        Tell CRIMSON that the timestep is complete.

        NetlistBoundaryManager owns the decision of when to call this. The
        adapter only forwards the call if the bridge has been loaded.
        """
        if self._bridge is not None:
            self._bridge.finalize_timestep(int(timestep))

    def _ensure_bridge(self, dt):
        """
        Load the bridge lazily so fake Rtilde/S tests never touch CRIMSON.
        """
        if self._bridge is None:
            self.load(dt)
        return self._bridge

    def _resolve_dt(self, dt):
        """
        Use the call-specific timestep or the adapter's fixed construction dt.
        """
        if dt is not None:
            return float(dt)
        if self.delt is None:
            raise ValueError("A timestep dt is required before loading the CRIMSON netlist bridge.")
        return float(self.delt)

    def _import_bridge_module(self):
        """
        Import the compiled nanobind module from the normal path or ext/build.
        """
        try:
            import crimson_starfish_bridge # type: ignore
            return crimson_starfish_bridge
        except ImportError:
            bridge_build_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ext", "build")
            if bridge_build_dir not in sys.path:
                sys.path.insert(0, bridge_build_dir)
            import crimson_starfish_bridge # type: ignore
            return crimson_starfish_bridge
