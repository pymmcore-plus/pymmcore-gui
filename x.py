from PyQt6.QtWidgets import QApplication, QMainWindow, QDockWidget, QTextEdit, QWidget, QVBoxLayout
import sys
from PyQt6.QtCore import Qt

class InnerMainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.top_dock = QDockWidget("Top Dock", self)
        self.top_dock.setWidget(QTextEdit("Top Dock Content"))
        self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, self.top_dock)

class OuterMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Create the inner main window
        self.inner_main_window = InnerMainWindow(self)

        # Wrap inner main window in a QWidget to set as central widget
        container = QWidget(self)
        layout = QVBoxLayout()
        layout.addWidget(self.inner_main_window)
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Add dockable widgets to outer main window
        self.left_dock = QDockWidget("Left Dock", self)
        self.left_dock.setWidget(QTextEdit("Left Dock Content"))
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.left_dock)

        self.right_dock = QDockWidget("Right Dock", self)
        self.right_dock.setWidget(QTextEdit("Right Dock Content"))
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.right_dock)

        self.bottom_dock = QDockWidget("Bottom Dock", self)
        self.bottom_dock.setWidget(QTextEdit("Bottom Dock Content"))
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.bottom_dock)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = OuterMainWindow()
    main_window.show()
    sys.exit(app.exec())