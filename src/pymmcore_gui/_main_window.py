from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QMainWindow


class MicroManagerGUI(QMainWindow):
    """Micro-Manager minimal GUI."""

    def __init__(
        self, *, mmcore: CMMCorePlus | None = None, config: str | None = None
    ) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setWindowTitle("Micro-Manager")

        # get global CMMCorePlus instance
        self._mmc = mmcore or CMMCorePlus.instance()
