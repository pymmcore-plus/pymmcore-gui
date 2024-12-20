from __future__ import annotations

from typing import cast

from pymmcore_plus import CMMCorePlus
from pymmcore_widgets import ImagePreview
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QMenu,
    QMenuBar,
    QVBoxLayout,
    QWidget,
)

from .actions._core_actions import CORE_ACTIONS
from .widgets._mm_console import MMConsole
from .widgets._toolbars import OCToolBar


class WindowMenu(QMenu):
    def __init__(self, parent: QWidget | None = None):
        super().__init__("Window", parent)


class MicroManagerGUI(QMainWindow):
    """Micro-Manager minimal GUI."""

    def __init__(
        self, *, mmcore: CMMCorePlus | None = None, config: str | None = None
    ) -> None:
        super().__init__()
        self.setWindowTitle("Micro-Manager")

        # get global CMMCorePlus instance
        self._mmc = mmc = mmcore or CMMCorePlus.instance()
        self._mmc.loadSystemConfiguration("tests/test_config.cfg")

        self._console = MMConsole(self)
        import pymmcore_plus
        import useq

        self._console.push(
            {
                **pymmcore_plus.__dict__,
                **useq.__dict__,
                "core": mmc,
                "mmcore": mmc,
                "mmc": mmc,
                "window": self,
            }
        )
        dw = QDockWidget(self)
        dw.setWidget(self._console)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dw)

        mb = cast("QMenuBar", self.menuBar())
        self._window_menu = WindowMenu(self)
        mb.addMenu(self._window_menu)

        # TOOLBARS =================================

        if tb := self.addToolBar("File"):
            for info in CORE_ACTIONS.values():
                tb.addAction(info.to_qaction(mmc, self))

        self.addToolBar(OCToolBar(mmc, self))

        # LAYOUT ======================================

        central_wdg = QWidget(self)
        layout = QVBoxLayout(central_wdg)
        self.setCentralWidget(central_wdg)
        layout.addWidget(ImagePreview(mmcore=self._mmc))
