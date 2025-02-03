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

    # clims, cmap, interpolation

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

    # attach/detach the widget from the core events
    with patch.object(
        img_preview, "_on_image_snapped", wraps=img_preview._on_image_snapped
    ) as mock_on_snapped:
        # this attach is necessary to reconnect the mocked method
        img_preview.attach(mmcore)

        mock_on_snapped.assert_not_called()
        with qtbot.waitSignal(mmcore.events.imageSnapped):
            mmcore.snapImage()
        mock_on_snapped.assert_called_once()
        mock_on_snapped.reset_mock()
        img_preview.detach()
        with qtbot.waitSignal(mmcore.events.imageSnapped):
            mmcore.snapImage()
        mock_on_snapped.assert_not_called()
