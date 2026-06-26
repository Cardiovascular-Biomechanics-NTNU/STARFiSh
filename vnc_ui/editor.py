import math
import os
import subprocess
import sys
from vnc_ui.qt_compat import QtWidgets, QtCore, QtGui
from UtilityLib.constants import newestNetworkXml as nxml
from vnc_ui.scene import VascularScene
from vnc_ui.scene_items import VesselEdge, JunctionNode
from vnc_ui.panels import PropertiesPanel
from vnc_ui.visualization_qt import QtVisualisationWidget

class VascularEditorWidget(QtWidgets.QWidget):
    def __init__(self, enable_visualization_tab=True):
        super().__init__()
        self._enable_visualization_tab = bool(enable_visualization_tab)

        self.scene = VascularScene()
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.setRenderHint(QtGui.QPainter.Antialiasing)
        self.scene.setSceneRect(-800, -800, 1600, 1600)
        self.view.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)

        # Zoom buttons
        zoom_layout = QtWidgets.QHBoxLayout()
        self.btn_zoom_in = QtWidgets.QPushButton("Zoom In")
        self.btn_zoom_out = QtWidgets.QPushButton("Zoom Out")
        self.btn_fit_screen = QtWidgets.QPushButton("Fit to Screen")
        
        self.cb_scale = QtWidgets.QComboBox()
        self.cb_scale.addItems(["1x", "2x", "5x", "10x", "15x"])
        self.cb_scale.setCurrentText("5x")
        self.cb_scale.currentTextChanged.connect(self.change_physical_scale)
        
        zoom_layout.addWidget(self.btn_zoom_in)
        zoom_layout.addWidget(self.btn_zoom_out)
        zoom_layout.addWidget(self.btn_fit_screen)
        zoom_layout.addWidget(QtWidgets.QLabel("  Visual Scale:"))
        zoom_layout.addWidget(self.cb_scale)
        zoom_layout.addStretch()

        self.btn_zoom_in.clicked.connect(self.zoom_in)
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.btn_fit_screen.clicked.connect(self.fit_to_screen)

        view_container = QtWidgets.QWidget()
        view_layout = QtWidgets.QVBoxLayout(view_container)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.addLayout(zoom_layout)
        view_layout.addWidget(self.view)

        # Use a QSplitter for the model builder layout and a scroll area for the right panel
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.prop_panel = PropertiesPanel(self.scene)
        self.prop_scroll = QtWidgets.QScrollArea()
        self.prop_scroll.setWidgetResizable(True)
        self.prop_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.prop_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.prop_scroll.setWidget(self.prop_panel)
        splitter.addWidget(view_container)
        splitter.addWidget(self.prop_scroll)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        self.prop_panel.setMinimumWidth(360)
        self.prop_scroll.setMinimumWidth(360)
        self.prop_scroll.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        self.prop_panel.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)

        self.prop_panel.btn_add_root.clicked.connect(self.add_root)
        self.prop_panel.btn_add_branch.clicked.connect(self.add_branch)
        self.prop_panel.btn_delete.clicked.connect(self.delete_selected)
        self.prop_panel.btn_save_project.clicked.connect(lambda: self.export_network_xml(export_layout=True))
        self.prop_panel.btn_export_model.clicked.connect(lambda: self.export_network_xml(export_layout=False))
        self.prop_panel.btn_load_project.clicked.connect(self.import_network_xml)

        # Tabs for model builder and visualization
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabPosition(QtWidgets.QTabWidget.North)
        self.tabs.tabBar().setExpanding(False)

        model_tab = QtWidgets.QWidget()
        model_layout = QtWidgets.QHBoxLayout(model_tab)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.addWidget(splitter)
        self.tabs.addTab(model_tab, "Model Parameters & Builder")

        # Add 3D Slicer Launcher Tab before result visualization.
        from vnc_ui.slicer_panel import SlicerLauncherPanel
        self.slicer_tab = SlicerLauncherPanel()
        self.slicer_tab.export_to_editor_requested.connect(self.import_from_slicer_topology)
        self.tabs.addTab(self.slicer_tab, "3D Slicer Integration")

        if self._enable_visualization_tab:
            visualization_tab = QtWidgets.QWidget()
            visualization_layout = QtWidgets.QVBoxLayout(visualization_tab)
            visualization_layout.setContentsMargins(0, 0, 0, 0)
            visualization_layout.setSpacing(0)

            self.visualizer_widget = QtVisualisationWidget()
            visualization_layout.addWidget(self.visualizer_widget)

            self.tabs.addTab(visualization_tab, "Result Visualization")
        else:
            self.visualizer_widget = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

        self.node_count = 0
        self.edge_count = 0

    def zoom_in(self):
        self.view.scale(1.2, 1.2)

    def zoom_out(self):
        self.view.scale(1 / 1.2, 1 / 1.2)

    def fit_to_screen(self):
        rect = self.scene.itemsBoundingRect()
        if rect.isEmpty():
            rect = self.scene.sceneRect()
        # Add a small margin so items aren't touching the exact edge
        margin = 50
        rect.adjust(-margin, -margin, margin, margin)
        self.view.fitInView(rect, QtCore.Qt.KeepAspectRatio)

    def change_physical_scale(self, text):
        val = float(text.replace("x", ""))
        self.scene.pixels_per_mm = val
        self.scene.enforce_fixed_lengths()
        # Ensure new layout bounds are updated
        rect = self.scene.itemsBoundingRect()
        if not rect.isEmpty():
            rect.adjust(-100, -100, 100, 100)
            self.scene.setSceneRect(rect)
            self.fit_to_screen()

    def add_root(self):
        self.node_count += 1
        node = JunctionNode(f"Junction {self.node_count}")
        center_point = self.view.mapToScene(self.view.viewport().rect().center())
        node.setPos(center_point)
        self.scene.addItem(node)

    def add_branch(self):
        """The easiest way to build trees. Spawns a child connected to the selected node."""
        selected = self.scene.selectedItems()
        nodes = [item for item in selected if isinstance(item, JunctionNode)]

        if not nodes:
            QtWidgets.QMessageBox.warning(self, "No Node Selected", "Please click a Junction Node to branch from.")
            return

        parent = nodes[0]
        self.node_count += 1
        self.edge_count += 1

        # Create new child
        child = JunctionNode(f"Junction {self.node_count}")

        # Initial guess position: place it slightly below and right to give it a starting angle
        offset = len(parent.outgoing_edges) * 30  # Fan out if multiple branches
        child.setPos(parent.scenePos().x() + 20 + offset, parent.scenePos().y() + 100)
        self.scene.addItem(child)

        # Create vessel
        edge = VesselEdge(parent, child, f"Vessel {self.edge_count}")
        self.scene.addItem(edge)

        # Enforce exact physical lengths, preserving the angle we just created
        self.scene.enforce_fixed_lengths()

        # Select the new edge so user can immediately edit its properties
        parent.setSelected(False)
        edge.setSelected(True)

    def delete_selected(self):
        for item in self.scene.selectedItems():
            if isinstance(item, VesselEdge):
                item.cleanup()
                self.scene.removeItem(item)

        for item in self.scene.selectedItems():
            if isinstance(item, JunctionNode):
                for edge in list(item.incoming_edges + item.outgoing_edges):
                    edge.cleanup()
                    self.scene.removeItem(edge)
                self.scene.removeItem(item)

    def setup_sample_network(self):
        self.node_count = 4
        self.edge_count = 3

        inlet_node = JunctionNode("Inlet Node")
        bifurcation_node = JunctionNode("Bifurcation Node")
        outlet1_node = JunctionNode("Outlet 1 Node")
        outlet2_node = JunctionNode("Outlet 2 Node")

        # The positions are just initial angles, the `enforce_fixed_lengths` will correct the distances
        inlet_node.setPos(0, -200)
        bifurcation_node.setPos(0, 0)
        outlet1_node.setPos(-100, 100)
        outlet2_node.setPos(100, 100)

        self.scene.addItem(inlet_node)
        self.scene.addItem(bifurcation_node)
        self.scene.addItem(outlet1_node)
        self.scene.addItem(outlet2_node)

        v1 = VesselEdge(inlet_node, bifurcation_node, "Main Artery")
        v2 = VesselEdge(bifurcation_node, outlet1_node, "Left Branch")
        v3 = VesselEdge(bifurcation_node, outlet2_node, "Right Branch")

        # Let's give them different physical lengths to demonstrate the feature!
        v1.length_mm = 15.0
        v2.length_mm = 8.0
        v3.length_mm = 12.0

        self.scene.addItem(v1)
        self.scene.addItem(v2)
        self.scene.addItem(v3)

        # Fix the layout immediately so it perfectly matches physical lengths
        self.scene.enforce_fixed_lengths()

        self.scene.setSceneRect(-800, -800, 1600, 1600)

    def import_from_slicer_topology(self, nodes_dict, edges_list):
        if self.scene.items():
            reply = QtWidgets.QMessageBox.question(
                self, 'Clear Canvas?',
                'Importing Slicer topology will replace the current model canvas. Proceed?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return

        # Clear existing
        for item in self.scene.items():
            if hasattr(item, "cleanup"):
                item.cleanup()
            self.scene.removeItem(item)
            
        self.node_count = 0
        self.edge_count = 0

        node_objects = {}

        # 1. Instantiate JunctionNodes
        for node_id, pos in nodes_dict.items():
            self.node_count += 1
            is_terminal = "(Inlet)" in node_id or "(Outlet)" in node_id
            label = "Terminal" if is_terminal else "Junction"
            
            node = JunctionNode(f"{label} {self.node_count}")
            node.setPos(pos["x"], pos["y"])
            self.scene.addItem(node)
            node_objects[node_id] = node

        # 2. Instantiate VesselEdges
        for edge in edges_list:
            self.edge_count += 1
            source_node = node_objects[edge["start"]]
            dest_node = node_objects[edge["end"]]
            
            vessel = VesselEdge(source_node, dest_node, f"Vessel {self.edge_count} (from {edge['branch_name']})")
            
            # Map physical parameters
            vessel.length_mm = edge["length_mm"]
            if "area_mm2" in edge:
                vessel.area_start_mm2 = edge["area_mm2"]
                vessel.area_end_mm2 = edge["area_mm2"]
            
            self.scene.addItem(vessel)

        # 3. Enforce layout and show canvas
        self.scene.enforce_fixed_lengths()
        rect = self.scene.itemsBoundingRect()
        if not rect.isEmpty():
            rect.adjust(-100, -100, 100, 100)
            self.scene.setSceneRect(rect)
            self.fit_to_screen()
        
        # Switch to the primary editor tab (index 0)
        self.tabs.setCurrentIndex(0)

    # --- Network import/export (full STARFiSh XML) ---
    def import_network_xml(self):
        from UtilityLib import moduleXML as mXML
        import json
        import tempfile

        fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import Network/Project", "", "STARFiSh Project/XML (*.starproj *.xml)")
        if not fname:
            return

        layout_data = None
        xml_file_to_load = fname

        # Handle .starproj container format
        temp_xml_file = None
        if fname.endswith('.starproj'):
            try:
                with open(fname, 'r') as f:
                    project_data = json.load(f)
                layout_data = project_data.get('layout')
                xml_content = project_data.get('xml')
                
                # Write embedded XML to a temporary file so moduleXML can parse it
                temp_xml_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xml')
                temp_xml_file.write(xml_content.encode('utf-8'))
                temp_xml_file.close()
                xml_file_to_load = temp_xml_file.name
                networkName = os.path.splitext(os.path.basename(fname))[0]
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, 'Error', f'Failed to load .starproj file: {e}')
                return
        else:
            # Fallback for loading raw .xml with optional legacy _layout.json
            networkName = os.path.splitext(os.path.basename(fname))[0]
            layout_fname = fname.replace('.xml', '_layout.json')
            if not layout_fname.endswith('_layout.json'):
                layout_fname += '_layout.json'
            if os.path.exists(layout_fname):
                try:
                    with open(layout_fname, 'r') as f:
                        layout_data = json.load(f)
                except Exception:
                    pass

        try:
            vascularNetwork = mXML.loadNetworkFromXML(networkName, networkXmlFile=xml_file_to_load)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'Error', f'Failed to load network: {e}')
            if temp_xml_file:
                os.unlink(temp_xml_file.name)
            return

        if temp_xml_file:
            os.unlink(temp_xml_file.name)

        # prepare network topology
        try:
            vascularNetwork.evaluateConnections()
            vascularNetwork.findStartAndEndNodes()
        except Exception:
            pass

        # clear current scene
        for it in list(self.scene.items()):
            if isinstance(it, VesselEdge) or isinstance(it, JunctionNode):
                try:
                    it.cleanup()
                except Exception:
                    pass
                self.scene.removeItem(it)

        # create scene nodes for each unique node id
        node_map = {}
        scene_node_by_name = {}
        nodes_ids = set()
        for vessel in vascularNetwork.vessels.values():
            if hasattr(vessel, 'startNode') and vessel.startNode is not None:
                nodes_ids.add(vessel.startNode)
            if hasattr(vessel, 'endNode') and vessel.endNode is not None:
                nodes_ids.add(vessel.endNode)

        if layout_data:
            for n_data in layout_data.get('nodes', []):
                node = JunctionNode(n_data['name'])
                node.setPos(n_data.get('x', 0), n_data.get('y', 0))
                self.scene.addItem(node)
                scene_node_by_name[n_data['name']] = node
        else:
            # position nodes on a circle for initial layout
            nodes_list = sorted(list(nodes_ids))
            n = len(nodes_list) if nodes_list else 1
            for i, nid in enumerate(nodes_list):
                angle = 2.0 * math.pi * i / n
                x = math.cos(angle) * 200
                y = math.sin(angle) * 200
                node = JunctionNode(f"Node {nid}")
                node.setPos(x, y)
                self.scene.addItem(node)
                node_map[nid] = node

        # create vessel edges
        edge_map = {}
        for vessel in vascularNetwork.vessels.values():
            # find start/end node objects
            s = None
            e = None
            if layout_data:
                e_data = next((ed for ed in layout_data.get('edges', []) if ed.get('vessel_id') == vessel.Id), None)
                if e_data:
                    s = scene_node_by_name.get(e_data.get('source_node_name'))
                    e = scene_node_by_name.get(e_data.get('dest_node_name'))
            else:
                try:
                    s = node_map.get(vessel.startNode, None)
                    e = node_map.get(vessel.endNode, None)
                except Exception:
                    pass
            if s is None:
                s = JunctionNode(f"start_{vessel.Id}")
                s.setPos(0, -200)
                self.scene.addItem(s)
            if e is None:
                e = JunctionNode(f"end_{vessel.Id}")
                e.setPos(0, 0)
                self.scene.addItem(e)

            edge = VesselEdge(s, e, vessel.name if vessel.name else f"Vessel {vessel.Id}")
            # set physical properties
            try:
                edge.length_mm = float(vessel.length) * 1000.0
            except Exception:
                pass
            try:
                edge.area_start_mm2 = math.pi * (float(vessel.radiusProximal) ** 2) * 1e6
                edge.area_end_mm2 = math.pi * (float(vessel.radiusDistal) ** 2) * 1e6
            except Exception:
                pass
            try:
                edge.geometry_type = vessel.geometryType
                edge.vessel_type = edge.geometry_type
            except Exception:
                pass
            try:
                edge.grid_points = int(vessel.N)
            except Exception:
                pass
            try:
                edge.angle_y_mother = float(vessel.angleYMother)
            except Exception:
                pass
            try:
                edge.compliance_type = vessel.complianceType
                edge.compliance_values_by_type[edge.compliance_type] = {}
                for field_name in nxml.vesselComplianceElements.get(edge.compliance_type, []):
                    if field_name == 'complianceType':
                        continue
                    edge.compliance_values_by_type[edge.compliance_type][field_name] = getattr(vessel, field_name, None)
            except Exception:
                pass
            try:
                edge.fluid_values = {
                    'applyGlobalFluid': getattr(vessel, 'applyGlobalFluid', True),
                    'my': getattr(vessel, 'my', None),
                    'rho': getattr(vessel, 'rho', None),
                    'gamma': getattr(vessel, 'gamma', None),
                }
            except Exception:
                pass
            edge.vessel_id = vessel.Id
            self.scene.addItem(edge)
            edge_map[vessel.Id] = edge

        # attach BCs to nodes based on vascularNetwork.boundaryConditions
        for vid, bc_list in vascularNetwork.boundaryConditions.items():
            edge = edge_map.get(vid)
            if edge is None:
                continue
            for bc in bc_list:
                name = bc.getVariableValue('name') if hasattr(bc, 'getVariableValue') else getattr(bc, 'name', None)
                if isinstance(name, (list, tuple)) and name:
                    name = name[0]
                if not name:
                    continue
                is_end = str(name).startswith('_')
                node = edge.dest_node if is_end else edge.source_node
                if node is None:
                    continue
                if not hasattr(node, 'boundary_conditions') or node.boundary_conditions is None:
                    node.boundary_conditions = []
                node.boundary_conditions.append(bc)
                if not hasattr(node, 'boundary_condition') or node.boundary_condition is None:
                    node.boundary_condition = bc

        # finalize
        self.scene.enforce_fixed_lengths()
        QtWidgets.QMessageBox.information(self, 'Imported', f'Imported network from {fname}')

    def export_network_xml(self, export_layout=True):
        from UtilityLib import moduleXML as mXML
        import NetworkLib.classVascularNetwork as cVascNw
        import json
        import tempfile

        # export full vascularNetwork XML from current scene
        if export_layout:
            title = "Save Project (.starproj)"
            file_filter = "STARFiSh Project Files (*.starproj)"
            default_name = "project.starproj"
        else:
            title = "Export Model XML"
            file_filter = "XML Files (*.xml)"
            default_name = "input.xml"

        fname, _ = QtWidgets.QFileDialog.getSaveFileName(self, title, default_name, file_filter)
        if not fname:
            return False
        case_dir = os.path.dirname(os.path.abspath(fname))

        # traverse scene to assign IDs and topology
        edges = [it for it in self.scene.items() if isinstance(it, VesselEdge)]
        # find roots (edges whose source node has no incoming edges)
        roots = [e for e in edges if len(e.source_node.incoming_edges) == 0]
        id_map = {}
        parent_children = {}
        next_id = 1
        from collections import deque
        q = deque(roots)
        visited = set()
        while q:
            e = q.popleft()
            if e in visited:
                continue
            visited.add(e)
            if e not in id_map:
                id_map[e] = next_id
                next_id += 1
            # children
            kids = e.dest_node.outgoing_edges
            parent_children[id_map[e]] = []
            for child in kids:
                if child not in id_map:
                    id_map[child] = next_id
                    next_id += 1
                parent_children[id_map[e]].append(id_map[child])
                q.append(child)

        # assign any remaining edges
        for e in edges:
            if e not in id_map:
                id_map[e] = next_id
                next_id += 1

        # construct vascularNetwork
        vascularNetwork = cVascNw.VascularNetwork()
        
        # Apply requested defaults for the top portion of input.xml
        vascularNetwork.totalTime = 1.0
        vascularNetwork.CFL = 0.5
        vascularNetwork.timeSaveBegin = 0.0
        vascularNetwork.minSaveDt = -1.0
        vascularNetwork.maxMemory = 5000.0
        vascularNetwork.gravitationalField = False
        vascularNetwork.gravityConstant = -9.81
        
        vascularNetwork.solvingSchemeField = 'MacCormack_Flux'
        vascularNetwork.rigidAreas = False
        vascularNetwork.simplifyEigenvalues = False
        vascularNetwork.riemannInvariantUnitBase = 'Pressure'
        vascularNetwork.automaticGridAdaptation = True
        
        vascularNetwork.initialsationMethod = 'Auto'
        vascularNetwork.initMeanFlow = 0.0
        vascularNetwork.initMeanPressure = 10000.0
        vascularNetwork.estimateWindkesselCompliance = 'No'
        vascularNetwork.compPercentageWK3 = 0.2
        vascularNetwork.compPercentageTree = 0.8
        vascularNetwork.compTotalSys = 4.895587352e-08
        
        vascularNetwork.globalFluid = {'my': 0.004, 'rho': 1040.0, 'gamma': 2.0}

        vesselData = {}
        # build vessel data entries
        for e, vid in id_map.items():
            name = e.name.replace(' ', '')
            length_m = float(e.length_mm) / 1000.0
            # radii from areas
            r0 = math.sqrt(max(1e-12, e.area_start_mm2 * 1e-6) / math.pi)
            r1 = math.sqrt(max(1e-12, e.area_end_mm2 * 1e-6) / math.pi)
            geometry_type = getattr(e, 'geometry_type', None) or getattr(e, 'vessel_type', None) or 'cone'
            grid_points = int(getattr(e, 'grid_points', max(2, int(max(2, e.length_mm)))))
            compliance_type = getattr(e, 'compliance_type', None) or 'Hayashi'
            vessel_entry = {
                'Id': vid,
                'name': name,
                'geometryType': geometry_type,
                'length': length_m,
                'radiusProximal': r0,
                'radiusDistal': r1,
                'N': grid_points,
                'complianceType': compliance_type,
                'angleYMother': getattr(e, 'angle_y_mother', 0.0),
            }
            compliance_values = getattr(e, 'compliance_values_by_type', {}).get(compliance_type, {})
            for field_name in nxml.vesselComplianceElements.get(compliance_type, []):
                if field_name == 'complianceType':
                    continue
                if field_name in compliance_values:
                    vessel_entry[field_name] = compliance_values[field_name]
            fluid_values = getattr(e, 'fluid_values', {})
            for field_name in nxml.vesselFluidElements:
                if field_name in fluid_values:
                    vessel_entry[field_name] = fluid_values[field_name]
            vesselData[vid] = vessel_entry

        # apply topology
        for parent_id, children in parent_children.items():
            if len(children) >= 1:
                vesselData[parent_id]['leftDaughter'] = children[0]
            if len(children) >= 2:
                vesselData[parent_id]['rightDaughter'] = children[1]

        vascularNetwork.updateNetwork({'vesselData': vesselData})

        # attach boundary conditions from nodes, respecting start/end positions
        boundary_by_vessel = {}
        netlist_entries = []
        nodes = [it for it in self.scene.items() if isinstance(it, JunctionNode)]
        for node in nodes:
            conditions = getattr(node, 'boundary_conditions', None)
            if not conditions:
                continue
            for bc in conditions:
                name = bc.getVariableValue('name') if hasattr(bc, 'getVariableValue') else getattr(bc, 'name', None)
                if isinstance(name, (list, tuple)) and name:
                    name = name[0]
                if not name:
                    continue
                is_end = str(name).startswith('_')
                if is_end:
                    edge = node.incoming_edges[0] if node.incoming_edges else None
                    if edge is None and node.outgoing_edges:
                        edge = node.outgoing_edges[0]
                else:
                    edge = node.outgoing_edges[0] if node.outgoing_edges else None
                    if edge is None and node.incoming_edges:
                        edge = node.incoming_edges[0]
                if edge is None:
                    continue
                vid = id_map.get(edge)
                if vid is None:
                    continue
                boundary_by_vessel.setdefault(vid, []).append(bc)
                if str(name).lstrip('_') == 'Netlist':
                    branch_dat = getattr(bc, 'branchDat', None)
                    if branch_dat is None or str(branch_dat).strip() == '':
                        QtWidgets.QMessageBox.critical(
                            self,
                            'Missing Netlist DAT',
                            'Netlist boundary on vessel {} is missing branchDat.'.format(vid),
                        )
                        return False

                    branch_dat = os.path.abspath(os.path.expanduser(str(branch_dat)))
                    try:
                        map_branch_dat = os.path.relpath(branch_dat, case_dir)
                    except ValueError:
                        map_branch_dat = branch_dat
                    junction_id = str(getattr(node, 'name', '') or '').strip()
                    if not junction_id or junction_id.lower() == 'junction':
                        junction_id = 'vessel{}_{}'.format(vid, 'end' if is_end else 'start')

                    netlist_entries.append({
                        'bc': bc,
                        'vesselId': vid,
                        'junctionId': junction_id,
                        'position': 'end' if is_end else 'start',
                        'flowSign': 1.0 if is_end else -1.0,
                        'branchDat': map_branch_dat,
                        'isHeartModel': bool(getattr(bc, 'isHeartModel', False)),
                    })

        netlist_entries.sort(key=lambda row: (int(row['vesselId']), row['position'], str(row['junctionId'])))
        netlist_map_rows = []
        for surface_id, entry in enumerate(netlist_entries):
            bc = entry['bc']
            bc.update({
                'surfaceId': surface_id,
                'flowSign': entry['flowSign'],
                'Rtilde': None,
                'S': 0.0,
            })
            netlist_map_rows.append({
                'surfaceId': surface_id,
                'vesselId': entry['vesselId'],
                'junctionId': entry['junctionId'],
                'position': entry['position'],
                'flowSign': entry['flowSign'],
                'branchDat': entry['branchDat'],
                'isHeartModel': entry['isHeartModel'],
            })

        for vid, bcs in boundary_by_vessel.items():
            vascularNetwork.boundaryConditions[vid] = list(bcs)

        # layout serialization
        layout_data = {
            'nodes': [],
            'edges': []
        }
        for item in self.scene.items():
            if isinstance(item, JunctionNode):
                layout_data['nodes'].append({
                    'name': item.name,
                    'x': item.x(),
                    'y': item.y()
                })
            elif isinstance(item, VesselEdge):
                layout_data['edges'].append({
                    'name': item.name,
                    'vessel_id': id_map.get(item, None),
                    'source_node_name': item.source_node.name if item.source_node else None,
                    'dest_node_name': item.dest_node.name if item.dest_node else None,
                })

        # write XML/JSON depending on mode
        try:
            if export_layout:
                # Save into a .starproj container (JSON wrapping layout and XML)
                temp_xml_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xml')
                temp_xml_file.close()
                mXML.writeNetworkToXML(vascularNetwork, dataNumber='xxx', networkXmlFile=temp_xml_file.name)
                
                with open(temp_xml_file.name, 'r') as f:
                    xml_content = f.read()
                os.unlink(temp_xml_file.name)
                
                project_data = {
                    'layout': layout_data,
                    'xml': xml_content
                }
                
                if not fname.endswith('.starproj'):
                    fname += '.starproj'
                    
                with open(fname, 'w') as f:
                    json.dump(project_data, f, indent=4)
                    
                QtWidgets.QMessageBox.information(self, 'Exported', f'Project saved to:\n{fname}')
                return True
            else:
                # Export raw XML Model
                mXML.writeNetworkToXML(vascularNetwork, dataNumber='xxx', networkXmlFile=fname)
                exported_files = [f'input XML: {fname}']
                
                if netlist_map_rows:
                    from UtilityLib import netlistSurfaceBuilder as nls_builder

                    map_file = os.path.join(case_dir, 'netlist_map.csv')
                    netlist_file = os.path.join(case_dir, 'netlist_surfaces.xml')
                    nls_builder.write_netlist_map(netlist_map_rows, map_file)
                    nls_builder.build_netlist_surfaces(netlist_map_rows, netlist_file, base_dir=case_dir)
                    exported_files.append(f'netlist map: {map_file}')
                    exported_files.append(f'netlist XML: {netlist_file}')
                QtWidgets.QMessageBox.information(self, 'Exported', 'Exported:\n{}'.format('\n'.join(exported_files)))
                return True
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'Error', f'Failed to export network: {e}')
            return False


class VascularEditor(QtWidgets.QMainWindow):
    def __init__(self, enable_visualization_tab=True):
        super().__init__()
        self.setWindowTitle('CRIMSON STARFISH - Vascular Network Editor')
        self.editor_widget = VascularEditorWidget(enable_visualization_tab=enable_visualization_tab)
        self.setCentralWidget(self.editor_widget)

    def closeEvent(self, event):
        buttons = getattr(QtWidgets.QMessageBox, "StandardButton", QtWidgets.QMessageBox)
        save = getattr(buttons, "Save")
        discard = getattr(buttons, "Discard")
        cancel = getattr(buttons, "Cancel")

        choice = QtWidgets.QMessageBox.question(
            self,
            "Close editor?",
            "Do you want to save your project before closing?",
            save | discard | cancel,
            save,
        )

        if choice == save:
            if self.editor_widget.export_network_xml():
                self.editor_widget.slicer_tab.close_slicer()
                event.accept()
            else:
                event.ignore()
            return

        if choice == discard:
            self.editor_widget.slicer_tab.close_slicer()
            event.accept()
            return

        event.ignore()
