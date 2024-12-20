"""Functions that accept a single core instance and do something."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus._pymmcore import CMMCore

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any, TypeAlias

    from pymmcore_plus import CMMCorePlus

    CoreFunc: TypeAlias = Callable[[CMMCorePlus], Any]


def snap_image(mmc: CMMCore) -> None:
    """Snap an image, stopping sequence if running."""
    if mmc.isSequenceRunning():
        mmc.stopSequenceAcquisition()
    mmc.snapImage()


def toggle_live(mmc: CMMCore) -> None:
    """Start or stop live mode."""
    if mmc.isSequenceRunning():
        mmc.stopSequenceAcquisition()
    else:
        mmc.startContinuousSequenceAcquisition(0)


clear_roi = CMMCore.clearROI
clear_circular_buffer = CMMCore.clearCircularBuffer
full_focus = CMMCore.fullFocus
