import qt
import slicer
from pathlib import Path

class STARFiShCenterlineDialog(qt.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("STARFiShCenterlineDialog")
        self.setWindowTitle("STARFiSh VMTK Helper")
        self.setMinimumWidth(500)
        self.resize(560, 700)
        self.setAttribute(qt.Qt.WA_DeleteOnClose)
        self.setWindowFlags(qt.Qt.Window)

        self.surfaceNode = None
        self.endpointsNode = None
        self.branchNodes = []
        self.branchReportRows = []
        
        # We use the underlying SlicerVMTK widget to do the heavy lifting
        slicer.util.selectModule("ExtractCenterline")
        self.vmtk_widget = slicer.modules.extractcenterline.widgetRepresentation()
        
        self._build_ui()
        self._apply_style()
        self._setup_vmtk_outputs()

    def closeEvent(self, event):
        self._set_view_interaction_mode()
        super().closeEvent(event)

    def _build_ui(self):
        layout = qt.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = qt.QLabel("STARFiSh VMTK Helper")
        title.setObjectName("panelTitle")
        subtitle = qt.QLabel("Load geometry, curate endpoints, then extract centerline branch lengths.")
        subtitle.setObjectName("panelSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # 1. Load Geometry
        geomGroup = qt.QGroupBox("1. Geometry")
        form = qt.QFormLayout(geomGroup)
        form.setFieldGrowthPolicy(qt.QFormLayout.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        geomRow = qt.QHBoxLayout()
        self.txtGeom = qt.QLineEdit()
        self.txtGeom.setReadOnly(True)
        self.txtGeom.setPlaceholderText("Select a .vtp or .stl file...")
        btnBrowse = qt.QPushButton("Browse")
        btnBrowse.clicked.connect(self.browse_geom)
        geomRow.addWidget(self.txtGeom)
        geomRow.addWidget(btnBrowse)
        form.addRow("3D file", geomRow)
        layout.addWidget(geomGroup)

        # 2. Endpoints
        epGroup = qt.QGroupBox("2. Endpoints")
        epLayout = qt.QVBoxLayout(epGroup)
        
        btnRow = qt.QHBoxLayout()
        self.btnAutoDetect = qt.QPushButton("Auto Detect Endpoints")
        self.btnAutoDetect.clicked.connect(self.auto_detect)
        self.btnPlace = qt.QPushButton("Place Manually")
        self.btnPlace.clicked.connect(self.place_endpoints)
        self.btnStop = qt.QPushButton("Select / Move")
        self.btnStop.clicked.connect(self.stop_placing)
        self.btnClear = qt.QPushButton("Clear")
        self.btnClear.clicked.connect(self.clear_endpoints)
        
        btnRow.addWidget(self.btnAutoDetect)
        btnRow.addWidget(self.btnPlace)
        btnRow.addWidget(self.btnStop)
        btnRow.addWidget(self.btnClear)
        epLayout.addLayout(btnRow)
        
        self.lblEpCount = qt.QLabel("Endpoints selected: 0")
        epLayout.addWidget(self.lblEpCount)
        
        # Endpoint List for easy deletion
        self.epList = qt.QListWidget()
        self.epList.setFixedHeight(100)
        self.epList.currentRowChanged.connect(self.select_endpoint_from_list)
        self.btnDeleteEp = qt.QPushButton("Delete Selected Endpoint")
        self.btnDeleteEp.clicked.connect(self.delete_selected_endpoint)
        
        epLayout.addWidget(self.epList)
        epLayout.addWidget(self.btnDeleteEp)
        layout.addWidget(epGroup)

        # 3. Generate
        self.btnGenerate = qt.QPushButton("CREATE NEW CURVE (APPLY)")
        self.btnGenerate.setObjectName("primaryButton")
        self.btnGenerate.clicked.connect(self.generate_curve)
        layout.addWidget(self.btnGenerate)

        # 4. Results
        resGroup = qt.QGroupBox("4. Branch Lengths & Areas")
        resLayout = qt.QVBoxLayout(resGroup)
        resLayout.setSpacing(8)
        self.branchTable = qt.QTableWidget()
        self.branchTable.setColumnCount(6)
        self.branchTable.setHorizontalHeaderLabels(["", "Branch", "Length", "Radius", "Area", "Groups"])
        self.branchTable.verticalHeader().setVisible(False)
        self.branchTable.setSelectionBehavior(qt.QAbstractItemView.SelectRows)
        self.branchTable.setSelectionMode(qt.QAbstractItemView.SingleSelection)
        self.branchTable.setEditTriggers(qt.QAbstractItemView.NoEditTriggers)
        self.branchTable.setAlternatingRowColors(True)
        self.branchTable.setMinimumHeight(170)
        self.branchTable.horizontalHeader().setStretchLastSection(True)
        self.branchTable.setColumnWidth(0, 34)
        self.branchTable.setColumnWidth(1, 110)
        self.branchTable.setColumnWidth(2, 90)
        self.branchTable.setColumnWidth(3, 90)
        self.branchTable.itemSelectionChanged.connect(self.select_branch_from_table)
        resLayout.addWidget(self.branchTable)

        self.btnSaveReport = qt.QPushButton("Save Branch Report")
        self.btnSaveReport.clicked.connect(self.save_branch_report)
        resLayout.addWidget(self.btnSaveReport)

        self.txtResults = qt.QTextEdit()
        self.txtResults.setReadOnly(True)
        self.txtResults.setFixedHeight(78)
        resLayout.addWidget(self.txtResults)
        layout.addWidget(resGroup)

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background: #2b2b2b;
                color: #f2f2f2;
                font-size: 13px;
            }
            QLabel#panelTitle {
                font-size: 22px;
                font-weight: 700;
                color: #ffffff;
            }
            QLabel#panelSubtitle {
                color: #c9d1d9;
                padding-bottom: 4px;
            }
            QGroupBox {
                border: 1px solid #4a4f58;
                border-radius: 6px;
                margin-top: 12px;
                padding: 12px 8px 8px 8px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #e7edf5;
            }
            QLineEdit, QTextEdit, QTableWidget {
                background: #1f2328;
                border: 1px solid #4a4f58;
                border-radius: 4px;
                color: #f2f2f2;
                selection-background-color: #2b5b84;
            }
            QPushButton {
                background: #3b414a;
                border: 1px solid #58606b;
                border-radius: 4px;
                color: #ffffff;
                min-height: 32px;
                padding: 6px 10px;
            }
            QPushButton:hover {
                background: #4a5360;
            }
            QPushButton:pressed {
                background: #2f363f;
            }
            QPushButton#primaryButton {
                background: #2b5b84;
                border: 1px solid #3e78aa;
                font-size: 14px;
                font-weight: 700;
                min-height: 42px;
            }
            QPushButton#primaryButton:hover {
                background: #326a9a;
            }
            QHeaderView::section {
                background: #343a43;
                border: 0;
                border-bottom: 1px solid #4a4f58;
                color: #dce6f1;
                padding: 5px;
                font-weight: 600;
            }
            QTableWidget {
                gridline-color: #3f4650;
                alternate-background-color: #252a31;
            }
        """)

    def _setup_vmtk_outputs(self):
        # We explicitly set VMTK outputs to NOT generate models or text properties
        # by accessing the node selectors in the VMTK widget.
        selectors_to_disable = [
            "outputNetworkModelSelector",
            "outputNetworkPropertiesTableSelector",
            "outputCenterlinePropertiesTableSelector",
            "outputPreprocessedSurfaceModelSelector",
            "outputMeshErrorsMarkupsSelector",
            "outputVoronoiDiagramModelSelector"
        ]
        
        for sel_name in selectors_to_disable:
            selector = self.vmtk_widget.findChild("qMRMLNodeComboBox", sel_name)
            if selector:
                selector.noneEnabled = True
                if hasattr(selector, 'setCurrentNodeID'):
                    selector.setCurrentNodeID("")
                else:
                    selector.currentNodeID = ""

        # Make sure Curve and Model output generates new nodes
        curve_sel = self.vmtk_widget.findChild("qMRMLNodeComboBox", "outputCenterlineCurveSelector")
        if curve_sel:
            curve_sel.renameEnabled = True
            
        model_sel = self.vmtk_widget.findChild("qMRMLNodeComboBox", "outputCenterlineModelSelector")
        if model_sel:
            model_sel.renameEnabled = True

    def browse_geom(self):
        path = qt.QFileDialog.getOpenFileName(self, "Select 3D Geometry", "", "3D Models (*.vtp *.stl *.obj)")
        if path:
            self.txtGeom.setText(path)
            if self.surfaceNode:
                slicer.mrmlScene.RemoveNode(self.surfaceNode)
            self.surfaceNode = slicer.util.loadModel(path)
            
            # Make the vessel translucent so centerlines are visible inside
            if self.surfaceNode and self.surfaceNode.GetDisplayNode():
                self.surfaceNode.GetDisplayNode().SetOpacity(0.4)
            
            # Hook the surface into VMTK widget
            surface_sel = self.vmtk_widget.findChild("qMRMLNodeComboBox", "inputSurfaceSelector")
            if surface_sel:
                surface_sel.setCurrentNode(self.surfaceNode)
                
            # Reset camera
            layout_manager = slicer.app.layoutManager()
            if layout_manager and layout_manager.threeDWidget(0):
                layout_manager.threeDWidget(0).threeDView().resetFocalPoint()

    def _ensure_endpoints(self):
        if not self.endpointsNode or slicer.mrmlScene.GetNodeByID(self.endpointsNode.GetID()) is None:
            self.endpointsNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "CenterlineEndpoints")
            # Observers to keep the list updated when points are placed or auto-detected
            self.endpointsNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointPositionDefinedEvent, self.refresh_ep_list)
            self.endpointsNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointRemovedEvent, self.refresh_ep_list)
            self.endpointsNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent, self.refresh_ep_list)
            self._configure_endpoint_display()
            
        # Hook into VMTK widget
        ep_sel = self.vmtk_widget.findChild("qMRMLNodeComboBox", "endPointsMarkupsSelector")
        if ep_sel:
            ep_sel.setCurrentNode(self.endpointsNode)
            
        return self.endpointsNode

    def _configure_endpoint_display(self):
        if not self.endpointsNode:
            return

        display_node = self.endpointsNode.GetDisplayNode()
        if not display_node:
            self.endpointsNode.CreateDefaultDisplayNodes()
            display_node = self.endpointsNode.GetDisplayNode()

        if display_node:
            display_node.SetVisibility(True)
            if hasattr(display_node, "SetSelectedColor"):
                display_node.SetSelectedColor(1.0, 0.2, 0.1)
            if hasattr(display_node, "SetColor"):
                display_node.SetColor(0.1, 0.8, 1.0)
            if hasattr(display_node, "SetGlyphScale"):
                display_node.SetGlyphScale(3.0)
            if hasattr(display_node, "SetTextScale"):
                display_node.SetTextScale(2.0)
            if hasattr(display_node, "SetPropertiesLabelVisibility"):
                display_node.SetPropertiesLabelVisibility(True)

    def _configure_curve_display(self, curve_node):
        display_node = curve_node.GetDisplayNode()
        if not display_node:
            curve_node.CreateDefaultDisplayNodes()
            display_node = curve_node.GetDisplayNode()

        if not display_node:
            return

        display_node.SetVisibility(True)
        if hasattr(display_node, "SetVisibility3D"):
            display_node.SetVisibility3D(True)
        if hasattr(display_node, "SetPropertiesLabelVisibility"):
            display_node.SetPropertiesLabelVisibility(False)
        if hasattr(display_node, "SetPointLabelsVisibility"):
            display_node.SetPointLabelsVisibility(False)
        if hasattr(display_node, "SetNameVisibility"):
            display_node.SetNameVisibility(False)
        if hasattr(display_node, "SetTextScale"):
            display_node.SetTextScale(2.2)
        if hasattr(display_node, "SetLineThickness"):
            display_node.SetLineThickness(1.0)

    def _branch_color(self, index):
        colors = [
            (0.90, 0.20, 0.18),
            (0.12, 0.48, 0.85),
            (0.90, 0.38, 0.12),
            (0.20, 0.70, 0.35),
            (0.75, 0.25, 0.85),
            (0.95, 0.78, 0.20),
            (0.10, 0.72, 0.72),
            (0.95, 0.45, 0.65),
            (0.62, 0.46, 0.28),
            (0.70, 0.70, 0.70),
        ]
        return colors[index % len(colors)]

    def _set_curve_color(self, curve_node, color):
        display_node = curve_node.GetDisplayNode()
        if display_node and hasattr(display_node, "SetColor"):
            display_node.SetColor(*color)

    def _populate_branch_table(self, branch_rows):
        self.branchTable.setRowCount(len(branch_rows))
        for row, branch in enumerate(branch_rows):
            color = branch["color"]
            swatch = qt.QLabel()
            swatch.setFixedSize(18, 18)
            swatch.setStyleSheet(
                "background: rgb(%d, %d, %d); border: 1px solid #111; border-radius: 3px;"
                % (int(color[0] * 255), int(color[1] * 255), int(color[2] * 255))
            )
            self.branchTable.setCellWidget(row, 0, swatch)

            name_item = qt.QTableWidgetItem(branch["name"])
            length_item = qt.QTableWidgetItem(f"{branch['length']:.1f} mm")
            radius_item = qt.QTableWidgetItem(f"{branch['radius']:.2f} mm")
            area_item = qt.QTableWidgetItem(f"{branch['area']:.2f} mm²")
            groups = f"In: {branch['inlet_group']} | Out: {branch['outlet_group']}"
            groups_item = qt.QTableWidgetItem(groups)
            self.branchTable.setItem(row, 1, name_item)
            self.branchTable.setItem(row, 2, length_item)
            self.branchTable.setItem(row, 3, radius_item)
            self.branchTable.setItem(row, 4, area_item)
            self.branchTable.setItem(row, 5, groups_item)
        self.branchTable.resizeRowsToContents()

    def select_branch_from_table(self):
        row = self.branchTable.currentRow()
        if row < 0 or row >= len(self.branchNodes):
            return

        for i, node in enumerate(self.branchNodes):
            display_node = node.GetDisplayNode()
            if not display_node:
                continue
            if hasattr(display_node, "SetSelected"):
                display_node.SetSelected(i == row)
            if hasattr(display_node, "SetLineThickness"):
                display_node.SetLineThickness(1.5 if i == row else 1.0)
            if hasattr(display_node, "SetPropertiesLabelVisibility"):
                display_node.SetPropertiesLabelVisibility(False)
            if hasattr(display_node, "SetPointLabelsVisibility"):
                display_node.SetPointLabelsVisibility(False)
            if hasattr(display_node, "SetNameVisibility"):
                display_node.SetNameVisibility(False)

    def _set_view_interaction_mode(self):
        interaction_node = slicer.app.applicationLogic().GetInteractionNode()
        interaction_node.SetPlaceModePersistence(0)
        interaction_node.SetCurrentInteractionMode(interaction_node.ViewTransform)

    def _remove_legacy_branch_label_nodes(self):
        for node in list(slicer.util.getNodesByClass("vtkMRMLMarkupsFiducialNode")):
            if node.GetName().startswith("CenterlineBranchLabels"):
                slicer.mrmlScene.RemoveNode(node)

    def _curve_endpoint_positions(self, curve_node):
        n = curve_node.GetNumberOfControlPoints()
        if n <= 0:
            return None

        start = [0.0, 0.0, 0.0]
        end = [0.0, 0.0, 0.0]
        curve_node.GetNthControlPointPositionWorld(0, start)
        curve_node.GetNthControlPointPositionWorld(n - 1, end)
        return start, end

    def _distance(self, a, b):
        return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5

    def _endpoint_group_name(self, connected_branches):
        if not connected_branches:
            return "Terminal"
        return ", ".join(connected_branches)

    def _branch_sort_key(self, name):
        try:
            return int(name.split()[-1])
        except Exception:
            return name

    def _add_branch_connectivity(self, branch_rows, tolerance_mm=2.0):
        for branch in branch_rows:
            branch["connected_to"] = []
            branch["inlet_group"] = "Terminal"
            branch["outlet_group"] = "Terminal"

        endpoints = []
        for branch in branch_rows:
            branch_endpoints = branch.get("endpoints")
            if not branch_endpoints:
                continue
            endpoints.append({"branch": branch, "side": "inlet", "position": branch_endpoints[0]})
            endpoints.append({"branch": branch, "side": "outlet", "position": branch_endpoints[1]})

        for endpoint in endpoints:
            connected_names = []
            for other in endpoints:
                if endpoint is other:
                    continue
                if endpoint["branch"] is other["branch"]:
                    continue
                if self._distance(endpoint["position"], other["position"]) <= tolerance_mm:
                    connected_names.append(other["branch"]["name"])

            unique_names = sorted(set(connected_names), key=self._branch_sort_key)
            if endpoint["side"] == "inlet":
                endpoint["branch"]["inlet_group"] = self._endpoint_group_name(unique_names)
            else:
                endpoint["branch"]["outlet_group"] = self._endpoint_group_name(unique_names)

        for branch in branch_rows:
            connected = []
            for group in (branch["inlet_group"], branch["outlet_group"]):
                if group == "Terminal":
                    continue
                connected.extend([name.strip() for name in group.split(",")])
            branch["connected_to"] = sorted(set(connected), key=self._branch_sort_key)

    def save_branch_report(self):
        if not self.branchReportRows:
            slicer.util.errorDisplay("Generate centerlines before saving a branch report.")
            return

        default_path = "starfish_centerline_report.starfish_slicer"
        path = qt.QFileDialog.getSaveFileName(
            self,
            "Save Branch Report",
            default_path,
            "STARFiSh Slicer Export (*.starfish_slicer)"
        )
        if not path:
            return

        report_rows = []
        for branch in self.branchReportRows:
            report_rows.append({
                "branch": branch["name"],
                "length_mm": branch["length"],
                "mean_radius_mm": branch["radius"],
                "mean_area_mm2": branch["area"],
                "inlet_connected_to": branch["inlet_group"],
                "outlet_connected_to": branch["outlet_group"],
                "connected_to": branch["connected_to"],
            })
        try:
            import json
            report_data = {
                "version": "1.0",
                "branches": report_rows
            }
            with open(path, "w") as f:
                json.dump(report_data, f, indent=4)
            
            self.txtResults.append(f"\nReport saved successfully to:\n{path}")
        except Exception as e:
            slicer.util.errorDisplay(f"Failed to save report: {str(e)}")

    def refresh_ep_list(self, caller=None, event=None):
        blocked = self.epList.blockSignals(True)
        self.epList.clear()
        if not self.endpointsNode:
            self.lblEpCount.setText("Endpoints selected: 0")
            self.epList.blockSignals(blocked)
            return
            
        n = self.endpointsNode.GetNumberOfControlPoints()
        self.lblEpCount.setText(f"Endpoints selected: {n}")
        for i in range(n):
            label = self.endpointsNode.GetNthControlPointLabel(i)
            self.epList.addItem(f"Endpoint {i}: {label}")
        self.epList.blockSignals(blocked)

    def select_endpoint_from_list(self, row):
        if not self.endpointsNode or row < 0:
            return

        n = self.endpointsNode.GetNumberOfControlPoints()
        for i in range(n):
            self.endpointsNode.SetNthControlPointSelected(i, i == row)
        self._set_view_interaction_mode()

    def delete_selected_endpoint(self):
        if not self.endpointsNode: return
        row = self.epList.currentRow()
        if row < 0:
            for i in range(self.endpointsNode.GetNumberOfControlPoints()):
                if self.endpointsNode.GetNthControlPointSelected(i):
                    row = i
                    break
        if row >= 0:
            self.endpointsNode.RemoveNthControlPoint(row)
            self.refresh_ep_list()
            self._set_view_interaction_mode()

    def auto_detect(self):
        if not self.surfaceNode:
            slicer.util.errorDisplay("Load a 3D file first.")
            return
            
        self._ensure_endpoints()
        auto_btn = self.vmtk_widget.findChild(qt.QPushButton, "autoDetectEndPointsPushButton")
        if auto_btn:
            self.txtResults.append("Auto-detecting endpoints...")
            slicer.app.processEvents()
            auto_btn.click()
            self.refresh_ep_list()
            self._force_transparency()
            self._configure_endpoint_display()
            self._set_view_interaction_mode()
        else:
            slicer.util.errorDisplay("Could not find VMTK Auto-Detect button.")

    def _force_transparency(self):
        # Force all models in the scene to be translucent (useful if VMTK generates preprocessed surfaces)
        model_nodes = slicer.util.getNodesByClass("vtkMRMLModelNode")
        for m_node in model_nodes:
            display_node = m_node.GetDisplayNode()
            if display_node:
                display_node.SetOpacity(0.4)

    def place_endpoints(self):
        self._ensure_endpoints()
        interaction_node = slicer.app.applicationLogic().GetInteractionNode()
        selection_node = slicer.app.applicationLogic().GetSelectionNode()
        
        selection_node.SetReferenceActivePlaceNodeClassName("vtkMRMLMarkupsFiducialNode")
        selection_node.SetReferenceActivePlaceNodeID(self.endpointsNode.GetID())
        interaction_node.SetPlaceModePersistence(1)
        interaction_node.SetCurrentInteractionMode(interaction_node.Place)
        self.show()
        self.raise_()

    def stop_placing(self):
        self._set_view_interaction_mode()
        self.refresh_ep_list()
        self.show()
        self.raise_()

    def clear_endpoints(self):
        if self.endpointsNode:
            self.endpointsNode.RemoveAllControlPoints()
        self.refresh_ep_list()

    def generate_curve(self):
        if not self.surfaceNode:
            slicer.util.errorDisplay("Load a 3D file first.")
            return
            
        self._ensure_endpoints()
        if self.endpointsNode.GetNumberOfControlPoints() < 2:
            slicer.util.errorDisplay("Need at least 2 endpoints.")
            return

        self._remove_legacy_branch_label_nodes()
            
        # Ensure we are generating new curve and model nodes
        curve_sel = self.vmtk_widget.findChild("qMRMLNodeComboBox", "outputCenterlineCurveSelector")
        if curve_sel:
            curve_sel.addNode() # Trigger 'Create new node'
            
        model_sel = self.vmtk_widget.findChild("qMRMLNodeComboBox", "outputCenterlineModelSelector")
        if model_sel:
            model_sel.addNode() # Trigger 'Create new node'
            
        apply_btn = self.vmtk_widget.findChild(qt.QPushButton, "applyButton")
        if apply_btn:
            self.txtResults.append("Computing centerlines... please wait.")
            slicer.app.processEvents()
            
            # Click VMTK's apply button
            apply_btn.click()
            
            # Find the generated curve node(s) and compute lengths
            self.txtResults.clear()
            self.txtResults.append("Extracted branches. Select a row to highlight a branch in the 3D view.")
            self.branchNodes = []
            self.branchReportRows = []
            branch_rows = []
            
            # 1. First, find the generated Centerline Model and build a point locator to find Radius
            import vtk
            radius_locator = None
            radius_array = None
            
            # SlicerVMTK typically names it "Centerline model"
            model_nodes = slicer.util.getNodesByClass("vtkMRMLModelNode")
            centerline_model = None
            for m in model_nodes:
                if m.GetDisplayNode() and "Centerline model" in m.GetName():
                    centerline_model = m
                    break
                    
            if centerline_model:
                # Hide the model so it doesn't clutter the view
                centerline_model.GetDisplayNode().SetVisibility(False)
                polyData = centerline_model.GetPolyData()
                if polyData:
                    radius_array = polyData.GetPointData().GetArray("Radius")
                    if radius_array:
                        radius_locator = vtk.vtkKdTreePointLocator()
                        radius_locator.SetDataSet(polyData)
                        radius_locator.BuildLocator()

            # 2. Iterate through curves, calculate length and lookup start/end areas
            curve_nodes = slicer.util.getNodesByClass("vtkMRMLMarkupsCurveNode")
            found = False
            branch_idx = 1
            for node in curve_nodes:
                if node == self.endpointsNode:
                    continue
                length = node.GetCurveLengthWorld()
                if length > 0:
                    found = True
                    
                    # Look up average radius along the branch
                    mean_radius = 0.0
                    mean_area = 0.0
                    if radius_locator and radius_array:
                        num_points = node.GetNumberOfControlPoints()
                        if num_points > 0:
                            sum_r = 0.0
                            for i in range(num_points):
                                pos = [0.0, 0.0, 0.0]
                                node.GetNthControlPointPositionWorld(i, pos)
                                idx = radius_locator.FindClosestPoint(pos)
                                sum_r += radius_array.GetTuple1(idx)
                            mean_radius = sum_r / num_points
                            mean_area = 3.1415926535 * (mean_radius ** 2)

                    # Rename the node so the length appears in the 3D view text label
                    new_name = f"Branch {branch_idx} ({length:.1f} mm)"
                    node.SetName(new_name)

                    self._configure_curve_display(node)
                    color = self._branch_color(branch_idx - 1)
                    self._set_curve_color(node, color)
                        
                    self.txtResults.append(f"{new_name} | R: {mean_radius:.2f} mm | A: {mean_area:.1f} mm²")
                    self.branchNodes.append(node)
                    branch_rows.append({
                        "name": f"Branch {branch_idx}",
                        "length": length,
                        "radius": mean_radius,
                        "area": mean_area,
                        "color": color,
                        "endpoints": self._curve_endpoint_positions(node),
                    })
                    branch_idx += 1
                    
            # Just in case VMTK generated a temporary preprocessed model, make it translucent too
            self._force_transparency()
                    
            if not found:
                self.txtResults.append("Failed to generate curves.")
            else:
                self._add_branch_connectivity(branch_rows)
                self.branchReportRows = branch_rows
                self._populate_branch_table(branch_rows)
        else:
            slicer.util.errorDisplay("Could not find VMTK Apply button.")


def show_custom_ui():
    global __starfish_slicer_dialog__
    main_window = slicer.util.mainWindow()
    
    # Hide the entire Slicer module panel on the left!
    if hasattr(main_window, 'moduleSelector') and main_window.moduleSelector():
        main_window.moduleSelector().setVisible(False)
    if hasattr(main_window, 'modulePanelDockWidget') and main_window.modulePanelDockWidget():
        main_window.modulePanelDockWidget().setVisible(False)

    for existing in main_window.findChildren(qt.QDialog, "STARFiShCenterlineDialog"):
        existing.close()
        existing.deleteLater()

    __starfish_slicer_dialog__ = STARFiShCenterlineDialog(main_window)
    __starfish_slicer_dialog__.show()
    __starfish_slicer_dialog__.raise_()
    __starfish_slicer_dialog__.activateWindow()

if __name__ == "__main__":
    show_custom_ui()
