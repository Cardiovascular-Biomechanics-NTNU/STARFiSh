
class SolverSetupGroup(QtWidgets.QGroupBox):
    def __init__(self, scene, parent=None):
        super().__init__("Setup Solver", parent)
        self.scene = scene
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)
        
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)
        
        # 1. Simulation Context
        sim_tab = QtWidgets.QWidget()
        sim_layout = QtWidgets.QFormLayout(sim_tab)
        self.totalTime = NoWheelDoubleSpinBox()
        self.totalTime.setRange(0.001, 1000.0)
        self.totalTime.setDecimals(3)
        self.totalTime.setValue(self.scene.global_solver_params['totalTime'])
        
        self.CFL = NoWheelDoubleSpinBox()
        self.CFL.setRange(0.01, 1.0)
        self.CFL.setSingleStep(0.1)
        self.CFL.setValue(self.scene.global_solver_params['CFL'])
        
        self.timeSaveBegin = NoWheelDoubleSpinBox()
        self.timeSaveBegin.setRange(0.0, 1000.0)
        self.timeSaveBegin.setValue(self.scene.global_solver_params['timeSaveBegin'])
        
        self.minSaveDt = NoWheelDoubleSpinBox()
        self.minSaveDt.setRange(-1.0, 1000.0)
        self.minSaveDt.setValue(self.scene.global_solver_params['minSaveDt'])
        
        self.maxMemory = NoWheelDoubleSpinBox()
        self.maxMemory.setRange(1.0, 100000.0)
        self.maxMemory.setValue(self.scene.global_solver_params['maxMemory'])
        
        self.gravitationalField = QtWidgets.QCheckBox()
        self.gravitationalField.setChecked(self.scene.global_solver_params['gravitationalField'])
        
        self.gravityConstant = NoWheelDoubleSpinBox()
        self.gravityConstant.setRange(-100.0, 100.0)
        self.gravityConstant.setValue(self.scene.global_solver_params['gravityConstant'])
        
        sim_layout.addRow("Total Time (s):", self.totalTime)
        sim_layout.addRow("CFL:", self.CFL)
        sim_layout.addRow("Time Save Begin (s):", self.timeSaveBegin)
        sim_layout.addRow("Min Save Dt (s):", self.minSaveDt)
        sim_layout.addRow("Max Memory (MB):", self.maxMemory)
        sim_layout.addRow("Gravitational Field:", self.gravitationalField)
        sim_layout.addRow("Gravity Constant (m s-2):", self.gravityConstant)
        
        self.tabs.addTab(sim_tab, "Context")
        
        # 2. Solver Calibration
        solv_tab = QtWidgets.QWidget()
        solv_layout = QtWidgets.QFormLayout(solv_tab)
        
        self.solvingSchemeField = NoWheelComboBox()
        self.solvingSchemeField.addItems(["MacCormack_Flux", "MacCormack", "Upwind"])
        self.solvingSchemeField.setCurrentText(self.scene.global_solver_params['solvingSchemeField'])
        
        self.rigidAreas = QtWidgets.QCheckBox()
        self.rigidAreas.setChecked(self.scene.global_solver_params['rigidAreas'])
        
        self.simplifyEigenvalues = QtWidgets.QCheckBox()
        self.simplifyEigenvalues.setChecked(self.scene.global_solver_params['simplifyEigenvalues'])
        
        self.riemannInvariantUnitBase = NoWheelComboBox()
        self.riemannInvariantUnitBase.addItems(["Pressure", "Velocity", "Flow"])
        self.riemannInvariantUnitBase.setCurrentText(self.scene.global_solver_params['riemannInvariantUnitBase'])
        
        self.automaticGridAdaptation = QtWidgets.QCheckBox()
        self.automaticGridAdaptation.setChecked(self.scene.global_solver_params['automaticGridAdaptation'])
        
        solv_layout.addRow("Solving Scheme:", self.solvingSchemeField)
        solv_layout.addRow("Rigid Areas:", self.rigidAreas)
        solv_layout.addRow("Simplify Eigenvalues:", self.simplifyEigenvalues)
        solv_layout.addRow("Riemann Invariant Unit:", self.riemannInvariantUnitBase)
        solv_layout.addRow("Auto Grid Adaptation:", self.automaticGridAdaptation)
        
        self.tabs.addTab(solv_tab, "Calibration")
        
        # 3. Initialization
        init_tab = QtWidgets.QWidget()
        init_layout = QtWidgets.QFormLayout(init_tab)
        
        self.initialsationMethod = NoWheelComboBox()
        self.initialsationMethod.addItems(["ConstantPressure", "Auto", "MeanFlow", "MeanPressure", "AutoLinearSystem"])
        self.initialsationMethod.setCurrentText(self.scene.global_solver_params['initialsationMethod'])
        
        self.initMeanFlow = NoWheelDoubleSpinBox()
        self.initMeanFlow.setRange(0.0, 100.0)
        self.initMeanFlow.setValue(self.scene.global_solver_params['initMeanFlow'])
        
        self.initMeanPressure = NoWheelDoubleSpinBox()
        self.initMeanPressure.setRange(0.0, 100000.0)
        self.initMeanPressure.setValue(self.scene.global_solver_params['initMeanPressure'])
        
        self.estimateWindkesselCompliance = NoWheelComboBox()
        self.estimateWindkesselCompliance.addItems(["No", "Yes"])
        self.estimateWindkesselCompliance.setCurrentText(self.scene.global_solver_params['estimateWindkesselCompliance'])
        
        self.compPercentageWK3 = NoWheelDoubleSpinBox()
        self.compPercentageWK3.setRange(0.0, 1.0)
        self.compPercentageWK3.setSingleStep(0.1)
        self.compPercentageWK3.setValue(self.scene.global_solver_params['compPercentageWK3'])
        
        self.compPercentageTree = NoWheelDoubleSpinBox()
        self.compPercentageTree.setRange(0.0, 1.0)
        self.compPercentageTree.setSingleStep(0.1)
        self.compPercentageTree.setValue(self.scene.global_solver_params['compPercentageTree'])
        
        self.compTotalSys = NoWheelDoubleSpinBox()
        self.compTotalSys.setRange(0.0, 1.0)
        self.compTotalSys.setDecimals(12)
        self.compTotalSys.setValue(self.scene.global_solver_params['compTotalSys'])
        
        init_layout.addRow("Method:", self.initialsationMethod)
        init_layout.addRow("Mean Flow:", self.initMeanFlow)
        init_layout.addRow("Mean Pressure:", self.initMeanPressure)
        init_layout.addRow("Est. WK Compliance:", self.estimateWindkesselCompliance)
        init_layout.addRow("Comp % WK3:", self.compPercentageWK3)
        init_layout.addRow("Comp % Tree:", self.compPercentageTree)
        init_layout.addRow("Comp Total Sys:", self.compTotalSys)
        
        self.tabs.addTab(init_tab, "Initialization")
        
        # 4. Global Fluid
        fluid_tab = QtWidgets.QWidget()
        fluid_layout = QtWidgets.QFormLayout(fluid_tab)
        
        self.my = NoWheelDoubleSpinBox()
        self.my.setRange(0.0001, 1.0)
        self.my.setDecimals(6)
        self.my.setValue(self.scene.global_solver_params['my'])
        
        self.rho = NoWheelDoubleSpinBox()
        self.rho.setRange(1.0, 10000.0)
        self.rho.setValue(self.scene.global_solver_params['rho'])
        
        self.gamma = NoWheelDoubleSpinBox()
        self.gamma.setRange(1.0, 10.0)
        self.gamma.setValue(self.scene.global_solver_params['gamma'])
        
        fluid_layout.addRow("Viscosity (my):", self.my)
        fluid_layout.addRow("Density (rho):", self.rho)
        fluid_layout.addRow("Profile (gamma):", self.gamma)
        
        self.tabs.addTab(fluid_tab, "Fluid")
        
        # Connect signals
        self.totalTime.valueChanged.connect(lambda v: self.update_param('totalTime', v))
        self.CFL.valueChanged.connect(lambda v: self.update_param('CFL', v))
        self.timeSaveBegin.valueChanged.connect(lambda v: self.update_param('timeSaveBegin', v))
        self.minSaveDt.valueChanged.connect(lambda v: self.update_param('minSaveDt', v))
        self.maxMemory.valueChanged.connect(lambda v: self.update_param('maxMemory', v))
        self.gravitationalField.toggled.connect(lambda v: self.update_param('gravitationalField', v))
        self.gravityConstant.valueChanged.connect(lambda v: self.update_param('gravityConstant', v))
        
        self.solvingSchemeField.currentTextChanged.connect(lambda v: self.update_param('solvingSchemeField', v))
        self.rigidAreas.toggled.connect(lambda v: self.update_param('rigidAreas', v))
        self.simplifyEigenvalues.toggled.connect(lambda v: self.update_param('simplifyEigenvalues', v))
        self.riemannInvariantUnitBase.currentTextChanged.connect(lambda v: self.update_param('riemannInvariantUnitBase', v))
        self.automaticGridAdaptation.toggled.connect(lambda v: self.update_param('automaticGridAdaptation', v))
        
        self.initialsationMethod.currentTextChanged.connect(lambda v: self.update_param('initialsationMethod', v))
        self.initMeanFlow.valueChanged.connect(lambda v: self.update_param('initMeanFlow', v))
        self.initMeanPressure.valueChanged.connect(lambda v: self.update_param('initMeanPressure', v))
        self.estimateWindkesselCompliance.currentTextChanged.connect(lambda v: self.update_param('estimateWindkesselCompliance', v))
        self.compPercentageWK3.valueChanged.connect(lambda v: self.update_param('compPercentageWK3', v))
        self.compPercentageTree.valueChanged.connect(lambda v: self.update_param('compPercentageTree', v))
        self.compTotalSys.valueChanged.connect(lambda v: self.update_param('compTotalSys', v))
        
        self.my.valueChanged.connect(lambda v: self.update_param('my', v))
        self.rho.valueChanged.connect(lambda v: self.update_param('rho', v))
        self.gamma.valueChanged.connect(lambda v: self.update_param('gamma', v))

    def update_param(self, key, value):
        self.scene.global_solver_params[key] = value
