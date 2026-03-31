from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_widgets import MDAWidget
from pymmcore_widgets.mda._save_widget import OME_TIFF

if TYPE_CHECKING:
    from pathlib import Path

    from pymmcore_plus import CMMCorePlus

    from pymmcore_gui._qt.QtWidgets import QWidget


class _MDAWidget(MDAWidget):
    """MDAWidget subclass that defaults to in-memory output and hides tiff-sequence."""

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent, mmcore=mmcore)
        self._hide_tiff_sequence()

    def _hide_tiff_sequence(self) -> None:
        """Remove the 'tiff-sequence' option from the save widget's writer combo."""
        combo = self.save_info._writer_combo
        for i in range(combo.count()):
            if combo.itemText(i) == "tiff-sequence":
                combo.removeItem(i)
                break
        combo.setCurrentText(OME_TIFF)

    def prepare_mda(self) -> bool | str | Path | None:
        output = super().prepare_mda()
        if output is None:
            output = "memory"
        return output
