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
    dark_palette.setColor(QtGui.QPalette.Window, QtGui.QColor(30, 30, 30))
    dark_palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.Base, QtGui.QColor(22, 22, 22))
    dark_palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(30, 30, 30))
    dark_palette.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.Button, QtGui.QColor(30, 30, 30))
    dark_palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
    dark_palette.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)
    app.setPalette(dark_palette)
    app.setStyleSheet("""
        QWidget {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", "Roboto", "Helvetica Neue", Arial, sans-serif;
            font-size: 13px;
        }
        
        QToolTip {
            color: #ffffff;
            background-color: #2a82da;
            border: 1px solid white;
        }
        
        /* Standardize Global Buttons */
        QPushButton {
            background-color: #202326; 
            color: #f5f7fa; 
            border: 1px solid #343b43;
            border-radius: 2px; 
            font-weight: 600; 
            padding: 6px 14px;
        }
        QPushButton:hover { 
            background-color: #29313a; 
            border-color: #4d5966; 
        }
        QPushButton:pressed { 
            background-color: #171a1d; 
        }
        QPushButton:disabled { 
            background-color: #252525; 
            color: #777777; 
            border-color: #3a3a3a; 
        }
        
        /* Standardize Primary Action Buttons (Dark Blue) */
        QPushButton#primaryButton, QPushButton#btn_add_root, QPushButton#btn_add_branch, QPushButton#btn_bc_add {
            background-color: #263f58; 
            border-color: #4b78a3;
        }
        QPushButton#primaryButton:hover, QPushButton#btn_add_root:hover, QPushButton#btn_add_branch:hover, QPushButton#btn_bc_add:hover {
            background-color: #30506f; 
            border-color: #5d8dbb;
        }
        
        /* Tab Styles for Better Depth and Contrast */
        QTabWidget::pane {
            border: 1px solid #343b43;
            background: #1e1e1e;
            top: -1px; /* hide line below active tab */
        }
        QTabBar::tab {
            background: #202326;
            color: #94a3b8;
            border: 1px solid #343b43;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 8px 16px;
            margin-right: 2px;
            font-weight: bold;
        }
        QTabBar::tab:hover {
            background: #29313a;
            color: #e2e8f0;
        }
        QTabBar::tab:selected {
            background: #1e1e1e;
            color: #ffffff;
            border-color: #343b43;
            border-top: 4px solid #4da3ff; /* Thicker, brighter accent color for active tab */
        }
        QTabBar::tab:!selected {
            margin-top: 2px; /* make non-selected tabs slightly lower */
        }

        /* Scrollbars */
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
