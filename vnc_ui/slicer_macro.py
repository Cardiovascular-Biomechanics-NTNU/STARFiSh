import sys
import os
import qt

try:
    import slicer
except ImportError:
    print("This macro script is designed to run exclusively inside 3D Slicer.")
    sys.exit(1)

def main():
    print("=====================================================")
    print("STARFiSh 3D Slicer Custom UI Initialization...")
    print("=====================================================")
    
    # 0. Configure Slicer UI Preferences (Dark Theme & 3D Only View)
    try:
        slicer.app.settings().setValue("Styles/StyleName", "Dark Slicer")
        if hasattr(slicer.app, 'styleManager'):
            slicer.app.styleManager().setCurrentStyle("Dark Slicer")
            
        # Set Layout to "3D Only"
        slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)
    except Exception as e:
        print(f"Warning: Could not set UI preferences: {e}")

    # 1. We launch the custom dialog script
    script_path = os.path.join(os.path.dirname(__file__), "slicer_centerline_ui.py")
    if os.path.exists(script_path):
        print(f"Executing custom UI script: {script_path}")
        with open(script_path, "r") as f:
            code = f.read()
        
        # We execute it in the globals environment to make sure __main__ behaves correctly
        exec(code, globals())
        
        # 2. Parse custom arguments and automatically pass to the custom UI if needed
        file_to_load = None
        if len(sys.argv) > 1:
            for arg in sys.argv:
                if (arg.lower().endswith('.stl') or arg.lower().endswith('.vtp')) and os.path.exists(arg):
                    file_to_load = arg
                    break
        
        if file_to_load:
            print(f"Automatically loading passed geometry: {file_to_load}")
            # If the dialog was created, it is stored in the global namespace
            if '__starfish_slicer_dialog__' in globals():
                dialog = globals()['__starfish_slicer_dialog__']
                dialog.txtGeom.setText(file_to_load)
                dialog.surfaceNode = slicer.util.loadModel(file_to_load)
                
                if dialog.surfaceNode and dialog.surfaceNode.GetDisplayNode():
                    dialog.surfaceNode.GetDisplayNode().SetOpacity(0.4)
                
                # Hook into VMTK widget
                surface_sel = dialog.vmtk_widget.findChild("qMRMLNodeComboBox", "inputSurfaceSelector")
                if surface_sel:
                    surface_sel.setCurrentNode(dialog.surfaceNode)
                    
                # Reset camera
                slicer.app.layoutManager().threeDWidget(0).threeDView().resetFocalPoint()

    else:
        print(f"ERROR: Could not find custom UI script at {script_path}")

if __name__ == "__main__":
    # Delay execution slightly to ensure Slicer's main window is fully ready
    qt.QTimer.singleShot(1000, main)
