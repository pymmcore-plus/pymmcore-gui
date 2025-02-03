from __future__ import annotations

from typing import TYPE_CHECKING

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
