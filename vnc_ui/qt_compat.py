try:
    from PySide6 import QtWidgets, QtCore, QtGui  # type: ignore
except Exception:
    import qt  # type: ignore
    QtWidgets = qt
    QtCore = qt
    QtGui = qt
