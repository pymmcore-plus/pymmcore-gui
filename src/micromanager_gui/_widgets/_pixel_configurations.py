from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pymmcore_plus.model import PixelSizeGroup
from pymmcore_widgets import PixelConfigurationWidget
from qtpy.QtWidgets import QHBoxLayout, QPushButton, QWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus


class _PixelConfigurationWidget(PixelConfigurationWidget):
    """A Subclass of PixelConfigurationWidget.

    Remove cancel button and hide the parent widget since this will become a
    dock widget.
    """

    def __init__(self, parent: QWidget, *, mmcore: CMMCorePlus | None = None):
        super().__init__(parent=parent, mmcore=mmcore)
        self._parent = parent

        # hide cancel button
        btns_layout = cast(QHBoxLayout, self.layout().children()[0])
        cancel_btn = cast(QPushButton, btns_layout.itemAt(1).widget())
        cancel_btn.hide()

    # remove close() method from _on_apply
    def _on_apply(self) -> None:
        """Update the pixel configuration."""
        # check if there are errors in the pixel configurations
        if self._check_for_errors():
            return

        # delete all the pixel size configurations
        for resolutionID in self._mmc.getAvailablePixelSizeConfigs():
            self._mmc.deletePixelSizeConfig(resolutionID)

        # create the new pixel size configurations
        px_groups = PixelSizeGroup(presets=self._value_to_dict(self.value()))
        px_groups.apply_to_core(self._mmc)

        self._parent.hide()
