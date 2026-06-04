"""Build CRIMSON ``netlist_surfaces.xml`` files from branch DAT netlists.

The CRIMSON netlist editor exports one branch at a time. STARFiSh/CRIMSON
runtime code expects one combined ``netlist_surfaces.xml`` file. This module
keeps the CRIMSON-style DAT-to-XML conversion explicit and adds a small
``netlist_map.csv`` layer that maps each STARFiSh vessel boundary to a CRIMSON
surface/circuit.
"""

import argparse
import csv
import os
import xml.etree.ElementTree as ET


MAP_FIELDS = [
    "surfaceId",
    "vesselId",
    "junctionId",
    "position",
    "flowSign",
    "branchDat",
    "isHeartModel",
]


def _read_next_valid_line(lines, index):
    """Return ``(tokens, new_index)`` while skipping comments and blank lines."""
    while index < len(lines):
        line = lines[index].strip()
        index += 1
        if not line or line.startswith("#"):
            continue
        return line.split(), index
    return None, index


def _control_type_from_dat(control_type):
    component_controls = {
        "l": "leftVentricularElastance",
        "bleed": "bleedResistance",
        "customPython": "customPython",
        "customPythonUnstressedVolume": "customPythonUnstressedVolume",
        "prescribedPeriodicFlow": "prescribedPeriodicFlow",
    }
    node_controls = {
        "customPython": "customPython",
        "prescribedPeriodicPressure": "prescribedPeriodicPressure",
    }
    return component_controls.get(control_type, node_controls.get(control_type, control_type))


def dat_file_to_circuit_elements(dat_path, first_circuit_index=1):
    """Convert one CRIMSON branch ``.dat`` file into circuit XML elements.

    A DAT file may contain more than one circuit. Circuit indices are rewritten
    consecutively starting at ``first_circuit_index`` so the combined output has
    deterministic ordering.
    """
    comp_type_map = {
        "r": "resistor",
        "c": "capacitor",
        "i": "inductor",
        "d": "diode",
        "t": "volumeTracking",
        "v": "volumeTrackingPressureChamber",
    }
    flow_type_map = {"f": "fixed", "t": "threeDInterface"}
    pressure_type_map = {"f": "fixed", "l": "leftVentricularPressure"}

    with open(dat_path, "r") as dat_file:
        lines = dat_file.readlines()

    circuits = []
    circuit_index = first_circuit_index
    idx = 0

    while idx < len(lines):
        parts, _test_idx = _read_next_valid_line(lines, idx)
        if not parts:
            break

        circuit_elem = ET.Element("circuit")
        ET.SubElement(circuit_elem, "circuitIndex").text = str(circuit_index)

        parts, idx = _read_next_valid_line(lines, idx)
        if not parts:
            break
        num_components = int(parts[0])

        components = []
        for component_number in range(num_components):
            comp_type, idx = _read_next_valid_line(lines, idx)
            start_node, idx = _read_next_valid_line(lines, idx)
            end_node, idx = _read_next_valid_line(lines, idx)
            params, idx = _read_next_valid_line(lines, idx)

            component = {
                "index": str(component_number + 1),
                "type_char": comp_type[0],
                "startNodeIndex": start_node[0],
                "endNodeIndex": end_node[0],
                "parameterValue": params[0],
            }
            if len(params) > 1:
                component["initialVolume"] = params[1]
            components.append(component)

        parts, idx = _read_next_valid_line(lines, idx)
        num_prescribed_pressures = int(parts[0])
        prescribed_pressure_nodes = []
        for _ in range(num_prescribed_pressures):
            parts, idx = _read_next_valid_line(lines, idx)
            prescribed_pressure_nodes.append(parts[0])

        prescribed_pressure_values = []
        for _ in range(num_prescribed_pressures):
            parts, idx = _read_next_valid_line(lines, idx)
            prescribed_pressure_values.append(parts[0])

        prescribed_pressure_types = []
        for _ in range(num_prescribed_pressures):
            parts, idx = _read_next_valid_line(lines, idx)
            prescribed_pressure_types.append(parts[0])

        parts, idx = _read_next_valid_line(lines, idx)
        num_prescribed_flows = int(parts[0])
        prescribed_flow_components = []
        for _ in range(num_prescribed_flows):
            parts, idx = _read_next_valid_line(lines, idx)
            prescribed_flow_components.append(parts[0])

        prescribed_flow_values = []
        for _ in range(num_prescribed_flows):
            parts, idx = _read_next_valid_line(lines, idx)
            prescribed_flow_values.append(parts[0])

        prescribed_flow_types = []
        for _ in range(num_prescribed_flows):
            parts, idx = _read_next_valid_line(lines, idx)
            prescribed_flow_types.append(parts[0])

        parts, idx = _read_next_valid_line(lines, idx)
        num_pressure_nodes = int(parts[0])
        initial_pressures = {}
        for _ in range(num_pressure_nodes):
            parts, idx = _read_next_valid_line(lines, idx)
            initial_pressures[parts[0]] = parts[1]

        parts, idx = _read_next_valid_line(lines, idx)
        node_at_3d_interface = parts[0]

        parts, idx = _read_next_valid_line(lines, idx)
        num_components_with_control = int(parts[0])
        component_controls = {}
        for _ in range(num_components_with_control):
            parts, idx = _read_next_valid_line(lines, idx)
            component_controls[parts[0]] = (parts[1], parts[2] if len(parts) > 2 else "")

        parts, idx = _read_next_valid_line(lines, idx)
        num_nodes_with_control = int(parts[0])
        node_controls = {}
        for _ in range(num_nodes_with_control):
            parts, idx = _read_next_valid_line(lines, idx)
            node_controls[parts[0]] = (parts[1], parts[2] if len(parts) > 2 else "")

        components_elem = ET.SubElement(circuit_elem, "components")
        for component in components:
            comp_elem = ET.SubElement(components_elem, "component")
            ET.SubElement(comp_elem, "index").text = component["index"]
            ET.SubElement(comp_elem, "type").text = comp_type_map.get(component["type_char"], "unknown")
            ET.SubElement(comp_elem, "startNodeIndex").text = component["startNodeIndex"]
            ET.SubElement(comp_elem, "endNodeIndex").text = component["endNodeIndex"]
            ET.SubElement(comp_elem, "parameterValue").text = component["parameterValue"]

            if "initialVolume" in component:
                ET.SubElement(comp_elem, "initialVolume").text = component["initialVolume"]

            if component["index"] in prescribed_flow_components:
                flow_index = prescribed_flow_components.index(component["index"])
                flow_type = prescribed_flow_types[flow_index]
                ET.SubElement(comp_elem, "prescribedFlowType").text = flow_type_map.get(flow_type, "unknown")
                if flow_type == "f":
                    ET.SubElement(comp_elem, "prescribedFlowValue").text = prescribed_flow_values[flow_index]

            if component["index"] in component_controls:
                control_type, control_source = component_controls[component["index"]]
                control_elem = ET.SubElement(comp_elem, "control")
                xml_control_type = _control_type_from_dat(control_type)
                ET.SubElement(control_elem, "type").text = xml_control_type
                if xml_control_type in (
                    "customPython",
                    "prescribedPeriodicFlow",
                    "customPythonUnstressedVolume",
                ):
                    ET.SubElement(control_elem, "source").text = control_source

        nodes_elem = ET.SubElement(circuit_elem, "nodes")
        for node_index, initial_pressure in initial_pressures.items():
            node_elem = ET.SubElement(nodes_elem, "node")
            ET.SubElement(node_elem, "index").text = node_index

            if node_index == node_at_3d_interface:
                ET.SubElement(node_elem, "isAt3DInterface").text = "true"

            if node_index in prescribed_pressure_nodes:
                pressure_index = prescribed_pressure_nodes.index(node_index)
                pressure_type = prescribed_pressure_types[pressure_index]
                ET.SubElement(node_elem, "prescribedPressureType").text = pressure_type_map.get(pressure_type, "unknown")
                initial_pressure = prescribed_pressure_values[pressure_index]

            ET.SubElement(node_elem, "initialPressure").text = initial_pressure

            if node_index in node_controls:
                control_type, control_source = node_controls[node_index]
                control_elem = ET.SubElement(node_elem, "control")
                xml_control_type = _control_type_from_dat(control_type)
                ET.SubElement(control_elem, "type").text = xml_control_type
                if xml_control_type in ("customPython", "prescribedPeriodicPressure"):
                    ET.SubElement(control_elem, "source").text = control_source

        circuits.append(circuit_elem)
        circuit_index += 1

    return circuits


def write_netlist_map(rows, output_csv):
    """Write the STARFiSh boundary-to-netlist map used by the builder."""
    with open(output_csv, "w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=MAP_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in MAP_FIELDS})


def read_netlist_map(map_csv, base_dir=None):
    """Read and validate ``netlist_map.csv`` rows."""
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(map_csv))

    rows = []
    seen_surface_ids = set()
    with open(map_csv, "r", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for line_number, row in enumerate(reader, start=2):
            surface_id = str(row.get("surfaceId", "")).strip()
            if not surface_id:
                raise ValueError("netlist_map.csv line {} has no surfaceId".format(line_number))
            if surface_id in seen_surface_ids:
                raise ValueError("netlist_map.csv repeats surfaceId {}".format(surface_id))
            seen_surface_ids.add(surface_id)

            branch_dat = str(row.get("branchDat", "")).strip()
            if not branch_dat:
                raise ValueError("netlist_map.csv line {} has no branchDat".format(line_number))
            if not os.path.isabs(branch_dat):
                branch_dat = os.path.join(base_dir, branch_dat)
            if not os.path.exists(branch_dat):
                raise FileNotFoundError("Netlist branch DAT not found: {}".format(branch_dat))

            position = str(row.get("position", "")).strip()
            if position not in ("0", "-1", "start", "end", "Start (0)", "End (-1)"):
                raise ValueError("Invalid netlist position for surfaceId {}: {}".format(surface_id, position))

            normalized = dict(row)
            normalized["surfaceId"] = surface_id
            normalized["branchDat"] = branch_dat
            normalized["position"] = "start" if position in ("0", "start", "Start (0)") else "end"
            rows.append(normalized)

    rows.sort(key=lambda item: int(float(item["surfaceId"])))
    return rows


def build_netlist_surfaces(rows_or_map_csv, output_xml, base_dir=None):
    """Build one combined ``netlist_surfaces.xml`` from mapped branch DAT files."""
    if isinstance(rows_or_map_csv, str):
        rows = read_netlist_map(rows_or_map_csv, base_dir=base_dir)
    else:
        rows = list(rows_or_map_csv)
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(output_xml))
        rows = _normalize_rows(rows, base_dir)

    root = ET.Element("netlistCircuits")
    next_circuit_index = 1
    for row in rows:
        circuits = dat_file_to_circuit_elements(row["branchDat"], first_circuit_index=next_circuit_index)
        for circuit in circuits:
            root.append(circuit)
        next_circuit_index += len(circuits)

    tree = ET.ElementTree(root)
    if hasattr(ET, "indent"):
        ET.indent(tree, space="\t", level=0)
    tree.write(output_xml, encoding="utf-8", xml_declaration=True)
    return output_xml


def _normalize_rows(rows, base_dir):
    normalized_rows = []
    seen_surface_ids = set()
    for row in rows:
        surface_id = str(row.get("surfaceId", "")).strip()
        if not surface_id:
            raise ValueError("A netlist map row has no surfaceId")
        if surface_id in seen_surface_ids:
            raise ValueError("Repeated netlist surfaceId {}".format(surface_id))
        seen_surface_ids.add(surface_id)

        branch_dat = str(row.get("branchDat", "")).strip()
        if not branch_dat:
            raise ValueError("Netlist surfaceId {} has no branchDat".format(surface_id))
        if not os.path.isabs(branch_dat):
            branch_dat = os.path.join(base_dir, branch_dat)
        if not os.path.exists(branch_dat):
            raise FileNotFoundError("Netlist branch DAT not found: {}".format(branch_dat))

        normalized = dict(row)
        normalized["surfaceId"] = surface_id
        normalized["branchDat"] = branch_dat
        normalized_rows.append(normalized)

    normalized_rows.sort(key=lambda item: int(float(item["surfaceId"])))
    return normalized_rows


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build CRIMSON netlist_surfaces.xml from netlist_map.csv or DAT files.")
    parser.add_argument("inputs", nargs="+", help="Either netlist_map.csv or one or more branch DAT files.")
    parser.add_argument("-o", "--output", default="netlist_surfaces.xml", help="Output XML path.")
    args = parser.parse_args(argv)

    if len(args.inputs) == 1 and args.inputs[0].lower().endswith(".csv"):
        build_netlist_surfaces(args.inputs[0], args.output)
    else:
        rows = [
            {
                "surfaceId": str(index),
                "vesselId": "",
                "junctionId": "",
                "position": "end",
                "flowSign": "1",
                "branchDat": input_path,
                "isHeartModel": "False",
            }
            for index, input_path in enumerate(args.inputs)
        ]
        build_netlist_surfaces(rows, args.output, base_dir=os.getcwd())


if __name__ == "__main__":
    main()
