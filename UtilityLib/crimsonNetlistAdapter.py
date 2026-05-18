import os
import sys
import xml.etree.ElementTree as ET


DEFAULT_CRIMSON_ROOT = "/home/sadid/crimson/cfs_reg/CRIMSONFlowsolver"


class CrimsonNetlistAdapter(object):
    """
    STARFiSh-side adapter boundary for CRIMSON netlist support.

    STARFiSh remains the primary 1D Python solver. CRIMSON is treated as a
    helper boundary-condition manager. This lightweight implementation proves
    that STARFiSh can locate and read CRIMSON netlist input. The internals can
    later be replaced by a pybind/nanobind wrapper around CRIMSON's NetlistCircuit
    or NetlistBoundaryCondition APIs without changing STARFiSh's solver loop.
    """

    def __init__(self, netlist_xml=None, crimson_root=None, hstep=1, alfi=1.0, delt=None):
        crimson_root = crimson_root or os.environ.get("CRIMSON_FLOWSOLVER_ROOT", DEFAULT_CRIMSON_ROOT)
        self.netlist_xml = os.path.abspath(netlist_xml or os.environ.get(
            "CRIMSON_NETLIST_XML",
            os.path.join(crimson_root, "netlist_surfaces.xml"),
        ))
        self.hstep = hstep
        self.alfi = alfi
        self.delt = delt
        self._bridge = None

    def summary(self):
        tree = ET.parse(self.netlist_xml)
        root = tree.getroot()

        circuits = root.findall("circuit")
        components = root.findall(".//component")
        interface_nodes = [
            node.findtext("index", default="?")
            for node in root.findall(".//node")
            if (node.findtext("isAt3DInterface", default="false") or "").lower() == "true"
        ]

        return {
            "file": self.netlist_xml,
            "circuit_count": len(circuits),
            "component_count": len(components),
            "interface_nodes": interface_nodes,
        }

    def hello(self):
        info = self.summary()
        return (
            "hello from CRIMSON netlist: "
            "{file} | circuits={circuit_count} | components={component_count} | "
            "3D/1D interface nodes={interface_nodes}"
        ).format(**info)

    def load(self, dt=None):
        dt = self._resolve_dt(dt)
        module = self._import_bridge_module()
        self._bridge = module.CrimsonBridge(self.hstep, self.alfi, dt)
        previous_cwd = os.getcwd()
        xml_dir = os.path.dirname(self.netlist_xml)
        try:
            if xml_dir:
                os.chdir(xml_dir)
            self._bridge.load(self.netlist_xml)
        finally:
            os.chdir(previous_cwd)
        return self

    def compute_implicit_coefficients(self, surface_id, timestep, time, dt, flow):
        bridge = self._ensure_bridge(dt)
        return bridge.compute_implicit_coefficients(int(timestep), float(time), float(dt), float(flow))

    def update_state(self, surface_id, timestep, time, dt, pressure, flow):
        bridge = self._ensure_bridge(dt)
        bridge.update_state(int(timestep), float(time), float(dt), float(pressure), float(flow))

    def finalize_timestep(self, timestep):
        if self._bridge is not None:
            self._bridge.finalize_timestep(int(timestep))

    def _ensure_bridge(self, dt):
        if self._bridge is None:
            self.load(dt)
        return self._bridge

    def _resolve_dt(self, dt):
        if dt is not None:
            return float(dt)
        if self.delt is None:
            raise ValueError("A timestep dt is required before loading the CRIMSON netlist bridge.")
        return float(self.delt)

    def _import_bridge_module(self):
        try:
            import crimson_starfish_bridge
            return crimson_starfish_bridge
        except ImportError:
            bridge_build_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ext", "build")
            if bridge_build_dir not in sys.path:
                sys.path.insert(0, bridge_build_dir)
            import crimson_starfish_bridge
            return crimson_starfish_bridge
