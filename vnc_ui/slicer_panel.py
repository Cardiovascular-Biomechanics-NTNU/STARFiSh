import os
import subprocess
import json
import csv
from PySide6 import QtWidgets, QtCore, QtGui

class ReportScene(QtWidgets.QGraphicsScene):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_enforcing = False

    def enforce_fixed_lengths(self):
        if self._is_enforcing:
            return
        self._is_enforcing = True

        PIXELS_PER_MM = 4.0
        nodes = [item for item in self.items() if isinstance(item, DraggableNode)]
        roots = [n for n in nodes if not n.incoming_edges]
        if not roots and nodes:
            roots = [nodes[0]]

        visited = set()
        def traverse_and_fix(node):
            if node in visited:
                return
            visited.add(node)
            for edge in node.outgoing_edges:
                child = edge.dest_node
                current_line = QtCore.QLineF(node.scenePos(), child.scenePos())
                if current_line.length() < 1.0:
                    current_line.setAngle(270)
                
                fixed_visual_length = edge.length_mm * PIXELS_PER_MM
                current_line.setLength(fixed_visual_length)
                
                child.setPos(current_line.p2())
                edge.update_position()
                traverse_and_fix(child)

        for root in roots:
            traverse_and_fix(root)
            
        self._is_enforcing = False

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QtGui.QColor("#d9dddc"))
        grid_size = 24
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)
        right = int(rect.right())
        bottom = int(rect.bottom())

        painter.setPen(QtGui.QPen(QtGui.QColor("#000000"), 1))
        x = left
        while x <= right:
            y = top
            while y <= bottom:
                painter.drawPoint(x, y)
                y += grid_size
            x += grid_size

class LinkedEdge(QtWidgets.QGraphicsLineItem):
    def __init__(self, source_node, dest_node, pen, label_text, length_mm):
        super().__init__()
        self.source_node = source_node
        self.dest_node = dest_node
        self.length_mm = length_mm
        self.setPen(pen)
        self.setZValue(1)
        
        self.bg_rect = QtWidgets.QGraphicsRectItem(self)
        self.bg_rect.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 200)))
        self.bg_rect.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        self.bg_rect.setZValue(2)
        
        self.label = QtWidgets.QGraphicsTextItem(f"{label_text}\n({length_mm:.1f} mm)", self)
        self.label.setDefaultTextColor(QtGui.QColor("#000000"))
        font = self.label.font()
        font.setPointSize(10)
        font.setBold(True)
        self.label.setFont(font)
        self.label.setZValue(3)
        
        self.update_position()

    def update_position(self):
        p1 = self.source_node.scenePos()
        p2 = self.dest_node.scenePos()
        self.setLine(QtCore.QLineF(p1, p2))
        
        mid_x = (p1.x() + p2.x()) / 2
        mid_y = (p1.y() + p2.y()) / 2
        
        br = self.label.boundingRect()
        self.bg_rect.setRect(
            mid_x - br.width()/2 - 4, 
            mid_y - br.height()/2 - 2, 
            br.width() + 8, 
            br.height() + 4
        )
        self.label.setPos(mid_x - br.width()/2, mid_y - br.height()/2)

class DraggableNode(QtWidgets.QGraphicsEllipseItem):
    def __init__(self, x, y, radius, pen, brush, label_text):
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.setPos(x, y)
        self.setPen(pen)
        self.setBrush(brush)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(4)
        
        self.incoming_edges = []
        self.outgoing_edges = []
        
        self.label = QtWidgets.QGraphicsTextItem(label_text, self)
        self.label.setDefaultTextColor(QtGui.QColor("#333333"))
        font = self.label.font()
        font.setPointSize(9)
        self.label.setFont(font)
        
        br = self.label.boundingRect()
        self.label.setPos(-br.width()/2, radius + 2)

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.ItemPositionHasChanged:
            scene = self.scene()
            if scene and hasattr(scene, "enforce_fixed_lengths"):
                scene.enforce_fixed_lengths()
            else:
                for edge in self.incoming_edges + self.outgoing_edges:
                    edge.update_position()
        return super().itemChange(change, value)

class SlicerLauncherPanel(QtWidgets.QWidget):
    export_to_editor_requested = QtCore.Signal(dict, list)

    def __init__(self):
        super().__init__()
        self.selected_file = None
        self.current_nodes = {}
        self.current_edges = []
        self.settings = QtCore.QSettings("STARFiSh", "SlicerIntegration")
        self.slicer_exec = self.load_slicer_executable()
        self.report_rows = []
        self.slicer_process = None
        
        outer_layout = QtWidgets.QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        outer_layout.addWidget(scroll)

        content = QtWidgets.QWidget()
        scroll.setWidget(content)

        main_layout = QtWidgets.QVBoxLayout(content)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(12)
        
        title = QtWidgets.QLabel("3D Centerline Extraction")
        title.setObjectName("panelTitle")
        
        desc = QtWidgets.QLabel(
            "Launch the STARFiSh Slicer helper to load vessel geometry, curate endpoints, "
            "extract centerlines, and review branch lengths."
        )
        desc.setObjectName("panelSubtitle")
        desc.setWordWrap(True)
        
        # 1. Geometry Import
        file_group = QtWidgets.QGroupBox("Geometry")
        file_layout = QtWidgets.QVBoxLayout(file_group)
        file_layout.setSpacing(8)
        
        self.txt_file = QtWidgets.QLineEdit()
        self.txt_file.setPlaceholderText("Optional .stl or .vtp file to load automatically")
        self.txt_file.setReadOnly(True)
        
        file_row = QtWidgets.QHBoxLayout()
        file_row.setSpacing(8)
        self.btn_select_file = QtWidgets.QPushButton("Browse")
        self.btn_select_file.clicked.connect(self.select_file)
        self.btn_clear_file = QtWidgets.QPushButton("Clear")
        self.btn_clear_file.clicked.connect(self.clear_file)
        
        file_row.addWidget(self.txt_file)
        file_row.addWidget(self.btn_select_file)
        file_row.addWidget(self.btn_clear_file)
        file_layout.addLayout(file_row)
        
        # 2. Slicer Launch
        launch_group = QtWidgets.QGroupBox("Slicer Helper")
        launch_layout = QtWidgets.QVBoxLayout(launch_group)
        launch_layout.setSpacing(10)
        
        self.lbl_slicer_path = QtWidgets.QLabel(self.slicer_status_text())
        self.lbl_slicer_path.setObjectName("pathLabel")
        self.lbl_slicer_path.setWordWrap(True)

        slicer_path_row = QtWidgets.QHBoxLayout()
        slicer_path_row.setSpacing(8)
        self.btn_choose_slicer = QtWidgets.QPushButton("Choose Slicer")
        self.btn_choose_slicer.clicked.connect(self.choose_slicer_executable)
        self.btn_use_bundled = QtWidgets.QPushButton("Use Bundled")
        self.btn_use_bundled.clicked.connect(self.use_bundled_slicer)
        slicer_path_row.addWidget(self.btn_choose_slicer)
        slicer_path_row.addWidget(self.btn_use_bundled)
        
        self.btn_launch_slicer = QtWidgets.QPushButton("Launch Slicer Helper")
        self.btn_launch_slicer.setObjectName("primaryButton")
        self.btn_launch_slicer.clicked.connect(self.launch_slicer)
        
        self.lbl_status = QtWidgets.QLabel("Ready.")
        self.lbl_status.setObjectName("statusLabel")
        self.lbl_status.setWordWrap(True)
        
        launch_layout.addWidget(self.lbl_slicer_path)
        launch_layout.addLayout(slicer_path_row)
        launch_layout.addWidget(self.btn_launch_slicer)
        launch_layout.addWidget(self.lbl_status)

        setup_group = QtWidgets.QGroupBox("Setup")
        setup_layout = QtWidgets.QVBoxLayout(setup_group)
        setup_layout.setSpacing(6)
        setup_text = QtWidgets.QLabel(
            "Linux bundled install: from the repository root, run "
            "`bash Slicer/install_slicer_linux.sh`.\n"
            "Manual install: install 3D Slicer for Linux, then install the SlicerVMTK "
            "extension from Slicer's Extensions Manager.\n"
            "After manual install, use Choose Slicer to select the Slicer executable."
        )
        setup_text.setObjectName("helpText")
        setup_text.setWordWrap(True)
        setup_layout.addWidget(setup_text)
        
        workflow_group = QtWidgets.QGroupBox("Workflow")
        workflow_layout = QtWidgets.QVBoxLayout(workflow_group)
        workflow_layout.setSpacing(6)
        for step in (
            "1. Load vessel geometry",
            "2. Generate or place endpoints",
            "3. Remove endpoints that do not belong",
            "4. Extract centerline curves",
            "5. Review branch lengths",
        ):
            label = QtWidgets.QLabel(step)
            label.setObjectName("workflowStep")
            workflow_layout.addWidget(label)

        report_group = QtWidgets.QGroupBox("Saved Centerline Report")
        report_layout = QtWidgets.QVBoxLayout(report_group)
        report_layout.setSpacing(8)

        report_actions = QtWidgets.QHBoxLayout()
        report_actions.setSpacing(8)
        self.btn_load_report = QtWidgets.QPushButton("Load Report")
        self.btn_load_report.clicked.connect(self.load_branch_report)
        self.btn_clear_report = QtWidgets.QPushButton("Clear Report")
        self.btn_clear_report.clicked.connect(self.clear_branch_report)
        self.btn_fit_screen = QtWidgets.QPushButton("Fit to Screen")
        self.btn_fit_screen.clicked.connect(self.fit_graph_to_screen)
        
        self.btn_export_canvas = QtWidgets.QPushButton("Export to Canvas")
        self.btn_export_canvas.setObjectName("primaryButton")
        self.btn_export_canvas.clicked.connect(self.export_to_canvas)
        
        report_actions.addWidget(self.btn_load_report)
        report_actions.addWidget(self.btn_clear_report)
        report_actions.addWidget(self.btn_fit_screen)
        report_actions.addStretch()
        report_actions.addWidget(self.btn_export_canvas)

        self.lbl_report_status = QtWidgets.QLabel("No saved centerline report loaded.")
        self.lbl_report_status.setObjectName("statusLabel")
        self.lbl_report_status.setWordWrap(True)

        self.report_table = QtWidgets.QTableWidget()
        self.report_table.setColumnCount(6)
        self.report_table.setHorizontalHeaderLabels(["Branch", "Length", "Radius", "Area", "Inlet", "Outlet"])
        self.report_table.verticalHeader().setVisible(False)
        self.report_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.report_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.report_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.report_table.setAlternatingRowColors(True)
        self.report_table.setMinimumHeight(130)
        self.report_table.setMaximumHeight(170)
        self.report_table.horizontalHeader().setStretchLastSection(True)
        self.report_table.setColumnWidth(0, 95)
        self.report_table.setColumnWidth(1, 80)
        self.report_table.setColumnWidth(2, 80)
        self.report_table.setColumnWidth(3, 80)

        self.report_scene = ReportScene(self)
        self.report_view = QtWidgets.QGraphicsView(self.report_scene)
        self.report_view.setMinimumHeight(800)
        self.report_view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.report_view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.report_view.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.report_view.setRenderHint(QtGui.QPainter.Antialiasing)
        self.report_view.setObjectName("reportGraph")

        report_layout.addLayout(report_actions)
        report_layout.addWidget(self.lbl_report_status)
        report_layout.addWidget(self.report_table, 0)
        report_layout.addWidget(self.report_view, 1)
        
        main_layout.addWidget(title)
        main_layout.addWidget(desc)
        main_layout.addWidget(setup_group)
        main_layout.addWidget(workflow_group)
        main_layout.addWidget(file_group)
        main_layout.addWidget(launch_group)
        main_layout.addWidget(report_group)

        self.apply_style()

    def closeEvent(self, event):
        self.close_slicer()
        super().closeEvent(event)

    def apply_style(self):
        self.setStyleSheet("""
            QWidget {
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
            QLineEdit, QTableWidget {
                background: #1f2328;
                border: 1px solid #4a4f58;
                border-radius: 4px;
                color: #f2f2f2;
                min-height: 32px;
                padding: 0 8px;
            }
            QGraphicsView {
                border: 1px solid #4a4f58;
                border-radius: 4px;
                min-height: 800px;
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
                min-height: 44px;
            }
            QPushButton#primaryButton:hover {
                background: #326a9a;
            }
            QLabel#statusLabel {
                color: #b8c0cc;
                font-style: italic;
            }
            QLabel#pathLabel {
                color: #b8c0cc;
                background: #1f2328;
                border: 1px solid #3f4650;
                border-radius: 4px;
                padding: 8px;
            }
            QLabel#workflowStep {
                background: #252a31;
                border: 1px solid #3f4650;
                border-radius: 4px;
                padding: 8px 10px;
                font-weight: 400;
            }
            QLabel#helpText {
                color: #c9d1d9;
                background: #252a31;
                border: 1px solid #3f4650;
                border-radius: 4px;
                padding: 10px;
                font-weight: 400;
                line-height: 1.35;
            }
        """)

    def load_slicer_executable(self):
        configured = self.settings.value("slicerExecutable", "", type=str)
        if configured and os.path.exists(configured):
            return configured
        return self.find_slicer_executable()

    def find_slicer_executable(self):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        slicer_dir = os.path.join(repo_root, "Slicer")
        slicer_exec = None

        if os.path.exists(slicer_dir):
            import glob
            matches = glob.glob(os.path.join(slicer_dir, "Slicer-*", "Slicer"))
            if matches:
                slicer_exec = matches[0]
            else:
                slicer_exec = os.path.join(slicer_dir, "Slicer")
        else:
            slicer_exec = os.path.join(repo_root, "Slicer")

        if os.name == 'nt':
            slicer_exec += ".exe"

        return slicer_exec

    def slicer_status_text(self):
        if self.slicer_exec and os.path.exists(self.slicer_exec):
            return f"Slicer executable: {self.slicer_exec}"
        return f"Slicer executable not found: {self.slicer_exec}"

    def update_slicer_status(self):
        self.lbl_slicer_path.setText(self.slicer_status_text())

    def choose_slicer_executable(self):
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Slicer Executable",
            os.path.dirname(self.slicer_exec) if self.slicer_exec else "",
            "Slicer executable (Slicer Slicer.exe);;All files (*)"
        )
        if fname:
            self.slicer_exec = fname
            self.settings.setValue("slicerExecutable", fname)
            self.update_slicer_status()

    def use_bundled_slicer(self):
        self.slicer_exec = self.find_slicer_executable()
        self.settings.remove("slicerExecutable")
        self.update_slicer_status()

    def select_file(self):
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select 3D Geometry", "", "3D Surface (*.stl *.vtp)")
        if fname:
            self.selected_file = fname
            self.txt_file.setText(fname)

    def clear_file(self):
        self.selected_file = None
        self.txt_file.clear()

    def load_branch_report(self):
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load Saved Centerline Report",
            "",
            "STARFiSh Slicer Export (*.starfish_slicer);;All files (*)"
        )
        if not fname:
            return

        try:
            rows = self.read_branch_report(fname)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Report Load Failed", f"Could not load report:\n{exc}")
            return

        self.report_rows = rows
        self.populate_report_table(rows)
        self.draw_report_graph(rows)
        self.lbl_report_status.setText(f"Loaded centerline report: {fname}")

    def clear_branch_report(self):
        self.report_rows = []
        self.report_table.setRowCount(0)
        self.report_scene.clear()
        self.lbl_report_status.setText("No saved centerline report loaded.")

    def fit_graph_to_screen(self):
        if not self.report_scene.items():
            return
        rect = self.report_scene.itemsBoundingRect().adjusted(-60, -60, 60, 60)
        self.report_view.fitInView(rect, QtCore.Qt.KeepAspectRatio)

    def export_to_canvas(self):
        if not self.current_nodes or not self.current_edges:
            QtWidgets.QMessageBox.warning(self, "No Graph", "Load a report first to generate a graph.")
            return
        self.export_to_editor_requested.emit(self.current_nodes, self.current_edges)

    def read_branch_report(self, path):
        if path.lower().endswith(".starfish_slicer") or path.lower().endswith(".json"):
            with open(path, "r") as f:
                data = json.load(f)
            raw_rows = data.get("branches", data if isinstance(data, list) else [])
        else:
            raise ValueError("Invalid file format. Please use a .starfish_slicer report saved from the STARFiSh Slicer helper.")

        rows = []
        for raw in raw_rows:
            rows.append({
                "branch": str(raw.get("branch", "")),
                "length_mm": self.as_float(raw.get("length_mm")),
                "mean_radius_mm": self.as_float(raw.get("mean_radius_mm")),
                "mean_area_mm2": self.as_float(raw.get("mean_area_mm2")),
                "inlet_connected_to": str(raw.get("inlet_connected_to", "Terminal") or "Terminal"),
                "outlet_connected_to": str(raw.get("outlet_connected_to", "Terminal") or "Terminal"),
            })
        return rows

    def as_float(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def populate_report_table(self, rows):
        self.report_table.setRowCount(len(rows))
        for row, branch in enumerate(rows):
            values = [
                branch["branch"],
                f"{branch['length_mm']:.1f} mm",
                f"{branch['mean_radius_mm']:.2f} mm",
                f"{branch['mean_area_mm2']:.2f} mm²",
                branch["inlet_connected_to"],
                branch["outlet_connected_to"],
            ]
            for col, value in enumerate(values):
                self.report_table.setItem(row, col, QtWidgets.QTableWidgetItem(value))
        self.report_table.resizeRowsToContents()

    def connected_branch_names(self, value):
        if not value or value == "Terminal":
            return []
        return [part.strip() for part in value.split(",") if part.strip() and part.strip() != "Terminal"]

    def draw_report_graph(self, rows):
        self.report_scene.clear()
        if not rows:
            return

        # 1. Identify nodes and edges (branches are edges, terminals/junctions are nodes)
        def get_canonical_id(branch_name, group_str, side):
            if not group_str or group_str == "Terminal":
                return f"{branch_name} ({side})"
            
            # Form a canonical junction name by combining all branches at this junction and sorting them
            members = [branch_name] + [m.strip() for m in group_str.split(",") if m.strip()]
            def sort_key(s):
                try:
                    return int(s.split()[-1])
                except:
                    return s
            members = sorted(list(set(members)), key=sort_key)
            return ", ".join(members)

        nodes = set()
        edges = []
        for index, branch in enumerate(rows):
            name = branch["branch"]
            in_group = branch["inlet_connected_to"]
            out_group = branch["outlet_connected_to"]
            
            start_id = get_canonical_id(name, in_group, "Inlet")
            end_id = get_canonical_id(name, out_group, "Outlet")
            
            nodes.add(start_id)
            nodes.add(end_id)
            edges.append({
                "branch_name": name,
                "start": start_id,
                "end": end_id,
                "index": index,
                "length_mm": branch["length_mm"],
                "area_mm2": branch["mean_area_mm2"]
            })

        # 2. Layout nodes: Junctions in the center, Terminals in an outer circle
        terminals = sorted([n for n in nodes if "(Inlet)" in n or "(Outlet)" in n])
        junctions = sorted([n for n in nodes if n not in terminals])
        
        positions = {}
        import math
        center_x, center_y = 0, 0
        
        # Inner circle for junctions
        j_radius = max(80, len(junctions) * 45)
        for i, node_id in enumerate(junctions):
            angle = i * 2 * math.pi / max(1, len(junctions))
            positions[node_id] = QtCore.QPointF(
                center_x + j_radius * math.cos(angle),
                center_y + j_radius * math.sin(angle)
            )
            
        # Outer circle for terminals
        t_radius = j_radius + 200
        for i, node_id in enumerate(terminals):
            angle = i * 2 * math.pi / max(1, len(terminals))
            positions[node_id] = QtCore.QPointF(
                center_x + t_radius * math.cos(angle),
                center_y + t_radius * math.sin(angle)
            )

        # 3. Create Draggable Nodes
        node_radius = 12
        node_items = {}
        for node_id in nodes:
            p = positions[node_id]
            is_terminal = "(Inlet)" in node_id or "(Outlet)" in node_id
            
            brush = QtGui.QBrush(QtGui.QColor("#ff4444") if is_terminal else QtGui.QColor("#4444ff"))
            pen = QtGui.QPen(QtGui.QColor("#000000"))
            pen.setWidth(2)
            
            label = "Terminal" if is_terminal else "Junction"
            node_item = DraggableNode(p.x(), p.y(), node_radius, pen, brush, label)
            self.report_scene.addItem(node_item)
            node_items[node_id] = node_item

        # 4. Create Linked Edges (Vessels)
        for edge in edges:
            source_node = node_items[edge["start"]]
            dest_node = node_items[edge["end"]]
            
            color = QtGui.QColor.fromHsv((edge["index"] * 43) % 360, 200, 180)
            pen = QtGui.QPen(color)
            pen.setWidth(5)
            pen.setCapStyle(QtCore.Qt.RoundCap)
            
            short_name = edge["branch_name"].replace("Branch ", "")
            edge_item = LinkedEdge(source_node, dest_node, pen, short_name, edge["length_mm"])
            self.report_scene.addItem(edge_item)
            
            # Register edge with nodes
            source_node.outgoing_edges.append(edge_item)
            dest_node.incoming_edges.append(edge_item)

        # Enforce exact physical lengths to initialize the layout geometrically
        self.report_scene.enforce_fixed_lengths()

        # Allow user to drag around freely within a reasonable scene rect bounds
        self.report_scene.setSceneRect(-4000, -4000, 8000, 8000)
        # Center the view initially on the generated layout
        initial_rect = self.report_scene.itemsBoundingRect().adjusted(-60, -60, 60, 60)
        self.report_view.fitInView(initial_rect, QtCore.Qt.KeepAspectRatio)
        
        # Save topology for export
        self.current_nodes = {node_id: {"x": positions[node_id].x(), "y": positions[node_id].y()} for node_id in nodes}
        self.current_edges = edges

    def close_slicer(self):
        if not self.slicer_process:
            return
        if self.slicer_process.poll() is not None:
            self.slicer_process = None
            return

        try:
            self.slicer_process.terminate()
            try:
                self.slicer_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.slicer_process.kill()
                self.slicer_process.wait(timeout=5)
        except Exception:
            pass
        finally:
            self.slicer_process = None

    def launch_slicer(self):
        macro_script = os.path.join(os.path.dirname(__file__), "slicer_macro.py")
        
        if not os.path.exists(macro_script):
            QtWidgets.QMessageBox.critical(self, "Error", "Macro script slicer_macro.py not found!")
            return
            
        cmd = [self.slicer_exec, "--python-script", macro_script]
        
        if self.selected_file and os.path.exists(self.selected_file):
            # We pass the geometry file as a custom arg to the script.
            # Slicer consumes arguments after a standalone script differently, 
            # so we just pass it and parse `sys.argv` inside the macro.
            cmd.extend([self.selected_file])
            
        self.lbl_status.setText(f"Launching Slicer helper from: {self.slicer_exec}")
        QtWidgets.QApplication.processEvents()
        
        try:
            # We use Popen instead of run() so it launches asynchronously and doesn't freeze the PySide6 UI!
            self.close_slicer()
            self.slicer_process = subprocess.Popen(cmd)
            self.lbl_status.setText("Slicer is running. Return here when finished.")
        except FileNotFoundError:
            self.lbl_status.setText("Error: Slicer executable not found in repo.")
            QtWidgets.QMessageBox.critical(
                self, 
                "Slicer Not Found", 
                f"Could not find 3D Slicer at expected path:\n{self.slicer_exec}\n\nPlease install Slicer into the 'Slicer' folder in the repository root."
            )
        except Exception as e:
            self.lbl_status.setText(f"Error launching Slicer: {e}")
