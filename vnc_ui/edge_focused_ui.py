import os
import sys

# Ensure repository root is on sys.path so sibling packages like UtilityLib import
cur = os.path.dirname(os.path.realpath(__file__))
repo_root = os.path.abspath(os.path.join(cur, '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from vnc_ui.qt_compat import QtWidgets, QtCore, QtGui

from vnc_ui.editor import VascularEditor


def main():
    app = QtWidgets.QApplication(sys.argv)

    # Apply a dark theme globally
    app.setStyle("Fusion")
    dark_palette = QtGui.QPalette()
    dark_palette.setColor(QtGui.QPalette.Window, QtGui.QColor(43, 43, 43))
    dark_palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.Base, QtGui.QColor(25, 25, 25))
    dark_palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(43, 43, 43))
    dark_palette.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.Button, QtGui.QColor(43, 43, 43))
    dark_palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
    dark_palette.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)
    app.setPalette(dark_palette)
    app.setStyleSheet("""
        QToolTip {
            color: #ffffff;
            background-color: #2a82da;
            border: 1px solid white;
        }
        QScrollBar:vertical {
            background: #2f2f2f;
            width: 14px;
            margin: 0;
            border-left: 1px solid #404040;
        }

        QScrollBar:horizontal {
            background: #2f2f2f;
            height: 14px;
            margin: 0;
            border-top: 1px solid #404040;
        }
        QScrollBar::handle:vertical,
        QScrollBar::handle:horizontal {
            background: #b8bec7;
            border-radius: 6px;
        }
        QScrollBar::handle:vertical {
            min-height: 32px;
        }
        QScrollBar::handle:horizontal {
            min-width: 32px;
        }
        QScrollBar::handle:vertical:hover,
        QScrollBar::handle:horizontal:hover {
            background: #d1d5db;
        }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical,
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {
            width: 0px;
            height: 0px;
            background: transparent;
        }
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical,
        QScrollBar::add-page:horizontal,
        QScrollBar::sub-page:horizontal {
            background: transparent;
        }
    """)

    editor = VascularEditor()
    editor.resize(1200, 800)
    editor.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
