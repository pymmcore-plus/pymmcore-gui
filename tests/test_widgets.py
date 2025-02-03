from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from pymmcore_gui.widgets._pygfx_image import PygfxImagePreview

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_image_preview(mmcore: CMMCorePlus, qtbot: QtBot) -> None:
    img_preview = PygfxImagePreview(None, mmcore)
    qtbot.addWidget(img_preview)
    assert img_preview.data is None
    mmcore.snapImage()
    assert img_preview.data is not None

    initial_clims = img_preview.clims
    img_preview.set_clims((0, 1000))
    assert img_preview.clims == (0, 1000)
    img_preview.set_clims("auto")
    assert img_preview.clims == initial_clims

    img_preview.set_cmap("viridis")
    assert "viridis" in img_preview.cmap.name

    assert img_preview.interpolation == "nearest"
    img_preview.set_interpolation("linear")
    assert img_preview.interpolation == "linear"

    with patch.object(img_preview, "set_data") as mock_callback:
        mmcore.startContinuousSequenceAcquisition(10)
        qtbot.wait(100)
        mmcore.stopSequenceAcquisition()
        while mmcore.isSequenceRunning():
            pass

    assert mock_callback.call_count > 5

    # detach the widget from the core
    img_preview.detach()
    with patch.object(img_preview, "_on_image_snapped") as mock_callback:
        mmcore.snapImage()
        mock_callback.assert_not_called()
