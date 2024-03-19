from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_widgets import CameraRoiWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from qtpy.QtWidgets import QWidget


class _CameraRoiWidget(CameraRoiWidget):
    """A subclass of CameraRoiWidget that sets a fixed height."""

    def __init__(self, parent: QWidget, *, mmcore: CMMCorePlus | None = None):
        super().__init__(parent=parent, mmcore=mmcore)

        self.setFixedHeight(self.minimumSizeHint().height())
