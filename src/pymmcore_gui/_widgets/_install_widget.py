from typing import Any

from pymmcore_widgets import InstallWidget
from qtpy.QtWidgets import QWidget


class _InstallWidget(InstallWidget):
    def __init__(self, parent: QWidget | None = None, **kwargs: Any) -> None:
        super().__init__(parent)
        self.resize(800, 400)
