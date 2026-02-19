from typing import Any

from pymmcore_widgets import MDAWidget


class _MDAWidget(MDAWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # remove "tiff-sequence" option since we don't know how to handle it in ndv yet
        combo = self.save_info._writer_combo
        combo.removeItem(combo.count() - 1)  # remove "tiff-sequence" option

        # default to ome-tiff
        index = combo.findText("ome-tiff")
        if index != -1:
            combo.setCurrentIndex(index)
