import os
os.environ["QT_LOGGING_RULES"] = "qt.svg.draw.warning=false;qt.svg.draw=false"

import sys
import h5py
import numpy as np
from vnc_ui.qt_compat import QtWidgets, QtCore, QtGui

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

# Import the minMaxFunction from STARFiSh
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from UtilityLib.processing import minMaxFunction

class CaseRowWidget(QtWidgets.QWidget):
    case_removed = QtCore.Signal(object)
    selection_changed = QtCore.Signal()

    def __init__(self, case_id, file_path, h5_file, parent=None):
        super().__init__(parent)
        self.case_id = case_id
        self.file_path = file_path
        self.h5_file = h5_file
        
        self.vessels_dict = {}
        self.sim_time = None
        
        if 'VascularNetwork' in self.h5_file:
            vn = self.h5_file['VascularNetwork']
            if 'simulationTime' in vn:
                self.sim_time = vn['simulationTime'][:]
        
        if 'vessels' in self.h5_file:
            for v_name, v_group in self.h5_file['vessels'].items():
                self.vessels_dict[v_name] = v_group
                
        self.setup_ui()
        
    def setup_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        
        self.lbl_case = QtWidgets.QLabel(f"<b>Case {self.case_id}</b>")
        self.lbl_case.setFixedWidth(60)
        
        filename = os.path.basename(self.file_path)
        self.lbl_file = QtWidgets.QLabel(filename)
        self.lbl_file.setMinimumWidth(150)
        
        self.cb_vessel = QtWidgets.QComboBox()
        self.cb_vessel.addItems(sorted(self.vessels_dict.keys()))
        self.cb_vessel.currentIndexChanged.connect(lambda _: self.selection_changed.emit())
        
        self.btn_remove = QtWidgets.QPushButton("✖")
        self.btn_remove.setFixedWidth(30)
        self.btn_remove.setToolTip("Remove Case")
        self.btn_remove.clicked.connect(lambda: self.case_removed.emit(self))
        
        layout.addWidget(self.lbl_case)
        layout.addWidget(self.lbl_file)
        layout.addWidget(QtWidgets.QLabel("Vessel:"))
        layout.addWidget(self.cb_vessel)
        layout.addWidget(self.btn_remove)
        layout.addStretch()

    def get_selected_vessel(self):
        vessel_name = self.cb_vessel.currentText()
        if vessel_name in self.vessels_dict:
            return vessel_name, self.vessels_dict[vessel_name]
        return None, None
        
    def close_file(self):
        if self.h5_file:
            self.h5_file.close()


class QtVisualisationWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.case_counter = 1
        self.variables = [
            'Plot P',
            'Plot Q',
            'Plot A',
            'Plot P,Q',
            'Plot Area, Compliance',
            'Plot CFL, wave speed'
        ]
        self.var_mapping = {
            'Plot P': ['Psol'],
            'Plot Q': ['Qsol'],
            'Plot A': ['Asol'],
            'Plot P,Q': ['Psol', 'Qsol'],
            'Plot Area, Compliance': ['Asol', 'Csol'],
            'Plot CFL, wave speed': ['CFL', 'csol']
        }

        self.setup_ui()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        controls_panel = QtWidgets.QWidget()
        controls_vbox = QtWidgets.QVBoxLayout(controls_panel)
        controls_vbox.setContentsMargins(0, 0, 0, 10)
        
        # Area for dynamic case rows
        self.cases_layout = QtWidgets.QVBoxLayout()
        controls_vbox.addLayout(self.cases_layout)
        
        # Add case button
        add_case_layout = QtWidgets.QHBoxLayout()
        self.btn_add_case = QtWidgets.QPushButton("Add Case")
        self.btn_add_case.clicked.connect(self.add_case)
        self.btn_add_case.setFixedWidth(120)
        
        self.btn_clear = QtWidgets.QPushButton("Clear All")
        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_clear.setFixedWidth(120)
        
        add_case_layout.addWidget(self.btn_add_case)
        add_case_layout.addWidget(self.btn_clear)
        add_case_layout.addStretch()
        controls_vbox.addLayout(add_case_layout)
        
        # Horizontal line separator
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        controls_vbox.addWidget(line)
        
        # Global controls
        global_controls_layout = QtWidgets.QHBoxLayout()
        
        self.cb_variable = QtWidgets.QComboBox()
        self.cb_variable.addItems(self.variables)
        self.cb_variable.currentIndexChanged.connect(self.update_plot_type)
        
        self.cb_plot_type = QtWidgets.QComboBox()
        self.cb_plot_type.addItems(["Time Series", "Spatial Profile"])
        self.cb_plot_type.currentIndexChanged.connect(self.update_plot_type)
        
        self.chk_legend = QtWidgets.QCheckBox("Show Legend")
        self.chk_legend.setChecked(True)
        self.chk_legend.stateChanged.connect(self.draw_plot)
        
        self.chk_minmax = QtWidgets.QCheckBox("MinMax points")
        self.chk_minmax.stateChanged.connect(self.draw_plot)
        
        global_controls_layout.addWidget(QtWidgets.QLabel("Variable:"))
        global_controls_layout.addWidget(self.cb_variable)
        global_controls_layout.addWidget(QtWidgets.QLabel("Plot Type:"))
        global_controls_layout.addWidget(self.cb_plot_type)
        global_controls_layout.addWidget(self.chk_legend)
        global_controls_layout.addWidget(self.chk_minmax)
        global_controls_layout.addStretch()
        controls_vbox.addLayout(global_controls_layout)

        # Slider Layout
        slider_layout = QtWidgets.QHBoxLayout()
        slider_layout.setContentsMargins(0, 5, 0, 0)

        self.slider_label = QtWidgets.QLabel("Node Index:")
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)
        self.slider.valueChanged.connect(self.on_slider_changed)
        
        self.slider_val_label = QtWidgets.QLabel("0")
        
        slider_layout.addWidget(self.slider_label)
        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(self.slider_val_label)
        slider_layout.addStretch()
        
        controls_vbox.addLayout(slider_layout)
        
        controls_panel.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        layout.addWidget(controls_panel)

        # Matplotlib Figure
        self.figure = Figure(dpi=150)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

    def add_case(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Solution Data File", "", "HDF5 Files (*.h5 *.hdf5);;All Files (*)"
        )
        if file_name:
            try:
                h5_file = h5py.File(file_name, 'r')
                row_widget = CaseRowWidget(self.case_counter, file_name, h5_file)
                self.case_counter += 1
                
                row_widget.case_removed.connect(self.remove_case)
                row_widget.selection_changed.connect(self.update_plot_type)
                
                self.cases_layout.addWidget(row_widget)
                self.update_plot_type()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error Loading File", f"Failed to parse HDF5: {e}")

    def clear_all(self):
        widgets = self.get_case_widgets()
        for w in widgets:
            self.remove_case(w)

    def remove_case(self, row_widget):
        row_widget.close_file()
        self.cases_layout.removeWidget(row_widget)
        row_widget.deleteLater()
        
        # If no cases left, reset counter to 1
        if self.cases_layout.count() == 0:
            self.case_counter = 1
            
        self.update_plot_type()

    def on_slider_changed(self, value):
        self.slider_val_label.setText(str(value))
        self.draw_plot()

    def get_case_widgets(self):
        widgets = []
        for i in range(self.cases_layout.count()):
            w = self.cases_layout.itemAt(i).widget()
            if isinstance(w, CaseRowWidget):
                widgets.append(w)
        return widgets

    def update_plot_type(self):
        variable = self.cb_variable.currentText()
        plot_type = self.cb_plot_type.currentText()
        var_keys = self.var_mapping.get(variable, [variable])
        
        case_widgets = self.get_case_widgets()
        if not case_widgets:
            self.draw_plot()
            return
            
        # Find the first valid data to set up the slider
        reference_data = None
        for cw in case_widgets:
            v_name, v_group = cw.get_selected_vessel()
            if v_group and var_keys[0] in v_group:
                reference_data = v_group[var_keys[0]][:]
                break
                
        if reference_data is None:
            self.draw_plot()
            return
        
        # Temporarily block signals to prevent drawing while configuring slider
        self.slider.blockSignals(True)
        
        if "Time Series" in plot_type:
            # Slider selects Node
            num_nodes = reference_data.shape[1]
            self.slider_label.setText("Node Index:")
            self.slider.setMaximum(max(0, num_nodes - 1))
            self.slider.setValue(num_nodes // 2)
            self.slider_val_label.setText(str(num_nodes // 2))
        elif "Spatial Profile" in plot_type:
            # Slider selects Time Step
            num_time_steps = reference_data.shape[0]
            self.slider_label.setText("Time Step:")
            self.slider.setMaximum(max(0, num_time_steps - 1))
            self.slider.setValue(max(0, num_time_steps - 1))
            self.slider_val_label.setText(str(max(0, num_time_steps - 1)))
            
        self.slider.blockSignals(False)
        self.draw_plot()

    def draw_plot(self):
        self.figure.clear()
        
        variable = self.cb_variable.currentText()
        plot_type = self.cb_plot_type.currentText()
        var_keys = self.var_mapping.get(variable, [variable])
        slider_val = self.slider.value()
        
        case_widgets = self.get_case_widgets()
        
        if not case_widgets:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "No cases loaded. Click 'Add Case' to begin.", 
                         ha='center', va='center', transform=ax.transAxes)
            self.canvas.draw()
            return
            
        axes = [self.figure.add_subplot(len(var_keys), 1, i+1) for i in range(len(var_keys))]
        
        plotted_anything = False
        show_legend = self.chk_legend.isChecked()
        show_minmax = self.chk_minmax.isChecked()
        
        for ax_idx, var_key in enumerate(var_keys):
            ax = axes[ax_idx]
            
            global_y_min = float('inf')
            global_y_max = float('-inf')
            
            for cw in case_widgets:
                vessel_name, v_group = cw.get_selected_vessel()
                if not v_group or var_key not in v_group:
                    continue

                data = v_group[var_key][:]
                case_label = f"Case {cw.case_id}: {vessel_name}"
                
                # Update global min and max for fixed Y-axis
                c_min = np.min(data)
                c_max = np.max(data)
                if c_min < global_y_min:
                    global_y_min = c_min
                if c_max > global_y_max:
                    global_y_max = c_max
                
                if "Time Series" in plot_type:
                    if cw.sim_time is not None:
                        t = cw.sim_time
                    else:
                        t = np.arange(data.shape[0])
                    
                    node_idx = min(slider_val, data.shape[1] - 1)
                    y = data[:, node_idx]
                    
                    line, = ax.plot(t, y, label=case_label)
                    
                    if show_minmax:
                        try:
                            # Plot minmax points using the STARFiSh utility function
                            mm_points = minMaxFunction(y, t, delta=0.025, seperateMinMax=False)
                            if mm_points and len(mm_points) == 2:
                                ax.plot(mm_points[1], mm_points[0], 'o', color=line.get_color(), markersize=4, alpha=0.5)
                        except Exception as e:
                            print(f"MinMax plot error: {e}")
                            
                    ax.set_xlabel("Time (s)")
                    ax.set_ylabel(var_key)
                    if ax_idx == 0:
                        ax.set_title(f"Plot over time (Node {node_idx})")
                    plotted_anything = True
                    
                elif "Spatial Profile" in plot_type:
                    length = v_group.attrs.get('length', None)
                    if length is not None:
                        # Length is usually in meters, convert to cm
                        x = np.linspace(0, length, data.shape[1]) * 100.0
                        xlabel = "Position (cm)"
                    elif 'x' in v_group:
                        x = v_group['x'][:]
                        xlabel = "Position (x)"
                    else:
                        x = np.arange(data.shape[1])
                        xlabel = "Node Index"
                        
                    time_idx = min(slider_val, data.shape[0] - 1)
                    y = data[time_idx, :]
                    
                    line, = ax.plot(x, y, label=case_label)
                    
                    if show_minmax:
                        try:
                            mm_points = minMaxFunction(y, x, delta=0.025, seperateMinMax=False)
                            if mm_points and len(mm_points) == 2:
                                ax.plot(mm_points[1], mm_points[0], 'o', color=line.get_color(), markersize=4, alpha=0.5)
                        except Exception as e:
                            print(f"MinMax plot error: {e}")
                    
                    ax.set_xlabel(xlabel)
                    ax.set_ylabel(var_key)
                    if ax_idx == 0:
                        ax.set_title(f"Plot along vessel (Time Step {time_idx})")
                    plotted_anything = True

            if show_legend and plotted_anything:
                ax.legend()
                
            if plotted_anything and global_y_min != float('inf') and global_y_max != float('-inf'):
                y_range = global_y_max - global_y_min
                if y_range == 0:
                    y_range = 1.0 # fallback if min == max
                # Apply 5% padding so lines don't hit the very top/bottom edges
                ax.set_ylim(global_y_min - 0.05 * y_range, global_y_max + 0.05 * y_range)
                
            if not plotted_anything:
                ax.text(0.5, 0.5, f"Variable '{var_key}' not found in selected vessels.", 
                             ha='center', va='center', transform=ax.transAxes)

        self.figure.tight_layout()
        self.canvas.draw()
