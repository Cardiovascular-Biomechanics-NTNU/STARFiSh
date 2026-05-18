class NetlistBoundaryManager(object):
    """
    Python-side coordination point for netlist boundary coupling.

    The first implementation stores constant coefficients from STARFiSh XML.
    Later this class should delegate coefficient computation and state updates
    to the compiled CRIMSON netlist adapter.
    """

    def __init__(self):
        self.boundaries = {}
        self.boundary_states = {}
        self.adapters = {}

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
        surface_id = int(surface_id)
        self.boundaries[surface_id] = {
            "vessel_id": vessel_id,
            "position": position,
            "netlist_file": netlist_file,
            "flow_sign": float(flow_sign),
            "rtilde": rtilde,
            "s": s,
        }

    def compute_coefficients(self, surface_id, timestep, time, dt, pressure, flow):
        surface_id = int(surface_id)
        boundary = self.boundaries.get(surface_id)
        if boundary is None:
            raise KeyError("No netlist boundary registered for surfaceId {}".format(surface_id))
        if boundary["rtilde"] is not None:
            return float(boundary["rtilde"]), float(boundary["s"])
        adapter = self._get_adapter(boundary, dt)
        return adapter.compute_implicit_coefficients(surface_id, timestep, time, dt, flow)

    def record_boundary_state(self, surface_id, timestep, time, dt, pressure, flow):
        self.boundary_states[int(surface_id)] = {
            "timestep": timestep,
            "time": time,
            "dt": dt,
            "pressure": pressure,
            "flow": flow,
        }
        boundary = self.boundaries.get(int(surface_id))
        if boundary is not None and boundary["rtilde"] is None:
            adapter = self._get_adapter(boundary, dt)
            adapter.update_state(surface_id, timestep, time, dt, pressure, flow)

    def finalize_timestep(self, timestep):
        for adapter in self.adapters.values():
            adapter.finalize_timestep(timestep)
        return None

    def _get_adapter(self, boundary, dt):
        netlist_file = boundary["netlist_file"]
        if netlist_file is None:
            raise ValueError("Netlist adapter mode requires netlistFile.")
        adapter = self.adapters.get(netlist_file)
        if adapter is None:
            from UtilityLib.crimsonNetlistAdapter import CrimsonNetlistAdapter
            adapter = CrimsonNetlistAdapter(netlist_file, delt=dt)
            adapter.load(dt)
            self.adapters[netlist_file] = adapter
        return adapter


_DEFAULT_MANAGER = NetlistBoundaryManager()


def get_default_netlist_manager():
    return _DEFAULT_MANAGER
