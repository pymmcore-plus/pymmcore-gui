from __future__ import annotations

from typing import TYPE_CHECKING

from fonticon_mdi6 import MDI6
from pymmcore_widgets import LiveButton, SnapButton
from qtpy.QtCore import QSize
from superqt.fonticon import icon

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from qtpy.QtWidgets import (
        QWidget,
    )

BTN_SIZE = 30
ICON_SIZE = QSize(25, 25)


class Snap(SnapButton):
    """A SnapButton."""

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent, mmcore=mmcore)
        self.setToolTip("Snap Image")
        self.setIcon(icon(MDI6.camera_outline))
        self.setText("")
        self.setFixedWidth(BTN_SIZE)
        self.setIconSize(ICON_SIZE)


class Live(LiveButton):
    """A LiveButton."""

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent, mmcore=mmcore)
        self.setToolTip("Live Mode")
        self.button_text_on = ""
        self.button_text_off = ""
        self.icon_color_on = ()
        self.icon_color_off = "magenta"
        self.setFixedWidth(BTN_SIZE)
        self.setIconSize(ICON_SIZE)
