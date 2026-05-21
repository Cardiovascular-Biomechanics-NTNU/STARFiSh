import os
import sys

import slicer
from slicer.ScriptedLoadableModule import ScriptedLoadableModule, ScriptedLoadableModuleWidget


class StarfishVNCUI(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "Starfish VNC UI"
        self.parent.categories = ["Starfish"]
        self.parent.dependencies = []
        self.parent.contributors = ["Starfish Team"]
        self.parent.helpText = "Vascular network editor with VMTK integration."
        self.parent.acknowledgementText = ""


class StarfishVNCUIWidget(ScriptedLoadableModuleWidget):
    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        from vnc_ui.editor import VascularEditorWidget

        self.editor = VascularEditorWidget(enable_visualization_tab=False)
        self.layout.addWidget(self.editor)
        self.layout.addStretch(1)

    def cleanup(self):
        if getattr(self, "editor", None) is not None:
            self.editor.setParent(None)
            self.editor.deleteLater()
            self.editor = None
