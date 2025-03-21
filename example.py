from pymmcore_plus import CMMCorePlus
from pymmcore_gui.widgets._pygfx_image import PygfxImagePreview
from PyQt6.QtWidgets import QDockWidget, QMainWindow, QApplication
from PyQt6.QtCore import Qt
from pymmcore_widgets import LiveButton

core = CMMCorePlus()
core.loadSystemConfiguration()
app = QApplication([])
wdg = QMainWindow()
dock = QDockWidget()
img = PygfxImagePreview(wdg, core)


snap_button = LiveButton()
dock.setWidget(snap_button)

wdg.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
wdg.setCentralWidget(img)
wdg.show()


app.exec()
