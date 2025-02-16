from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDockWidget, QMainWindow, QTabWidget, QWidget

from pymmcore_gui.widgets.image_preview._ndv_preview import NDVPreview


class ViewersDockingArea(QMainWindow):
    """Docking area for the viewers."""

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ):
        super().__init__(parent)
        self.setWindowTitle("Viewers")

        self.setTabPosition(
            Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North
        )

        # get global CMMCorePlus instance
        self._mmc = mmcore or CMMCorePlus.instance()

        _img_preview = NDVPreview(self, mmcore=self._mmc)
        self._img_preview_dock = QDockWidget("Preview")
        self._img_preview_dock.setWidget(_img_preview)
        self._img_preview_dock.setAllowedAreas(Qt.DockWidgetArea.TopDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, self._img_preview_dock)


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    app = QApplication([])

    _main = ViewersDockingArea()
    _main.show()

    app.exec()
