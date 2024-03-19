from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from micromanager_gui import MicroManagerGUI

mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()
gui = MicroManagerGUI()
gui.show()

app = QApplication.instance()
app.setStyle("Fusion")
