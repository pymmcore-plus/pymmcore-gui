from abc import abstractmethod
from contextlib import suppress

import numpy as np
from pymmcore_plus import CMMCorePlus
from PyQt6.QtCore import Qt, QTimerEvent
from PyQt6.QtWidgets import QWidget

_DEFAULT_WAIT = 10

__all__ = ["_ImagePreviewBase"]


class _ImagePreviewBase(QWidget):
    def __init__(
        self,
        parent: QWidget | None,
        mmcore: CMMCorePlus,
        *,
        use_with_mda: bool = False,
    ):
        super().__init__(parent)
        self._timer_id: int | None = None  # timer for streaming

        self.use_with_mda = use_with_mda
        self._is_mda_running: bool = False
        self._mmc: CMMCorePlus | None = mmcore
        self.attach(mmcore)

    def attach(self, core: CMMCorePlus) -> None:
        """Attach this widget to events in `core`."""
        if self._mmc is not None:
            self.detach()

        ev = core.events
        ev.imageSnapped.connect(self._on_image_snapped)
        ev.continuousSequenceAcquisitionStarted.connect(self._on_streaming_start)
        ev.sequenceAcquisitionStarted.connect(self._on_streaming_start)
        ev.sequenceAcquisitionStopped.connect(self._on_streaming_stop)
        ev.exposureChanged.connect(self._on_exposure_changed)
        ev.systemConfigurationLoaded.connect(self._on_system_config_loaded)
        ev.roiSet.connect(self._on_roi_set)
        ev.propertyChanged.connect(self._on_property_changed)
        core.mda.events.sequenceStarted.connect(
            lambda: setattr(self, "_is_mda_running", True)
        )
        core.mda.events.sequenceFinished.connect(
            lambda: setattr(self, "_is_mda_running", False)
        )

        self._mmc = core

    def detach(self) -> None:
        """Detach this widget from events in `core`."""
        if self._mmc is None:
            return
        with suppress(Exception):
            ev, self._mmc = self._mmc.events, None
            ev.imageSnapped.disconnect(self._on_image_snapped)
            ev.continuousSequenceAcquisitionStarted.disconnect(self._on_streaming_start)
            ev.sequenceAcquisitionStarted.disconnect(self._on_streaming_start)
            ev.sequenceAcquisitionStopped.disconnect(self._on_streaming_stop)
            ev.exposureChanged.disconnect(self._on_exposure_changed)

    @abstractmethod
    def set_data(self, data: np.ndarray) -> None:
        """Set texture data.

        The dtype must be compatible with wgpu texture formats.
        Will also apply contrast limits if _clims is "auto".
        """
        raise NotImplementedError

    # ----------------------------

    def _on_exposure_changed(self, device: str, value: str) -> None:
        # change timer interval
        if self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = self.startTimer(int(value), Qt.TimerType.PreciseTimer)

    def timerEvent(self, a0: QTimerEvent | None) -> None:
        if (core := self._mmc) and core.getRemainingImageCount() > 0:
            img = core.getLastImage()
            self.set_data(img)

    def _on_image_snapped(self) -> None:
        if (core := self._mmc) is None:
            return  # pragma: no cover
        if not self.use_with_mda and self._is_mda_running:
            return  # pragma: no cover

        last = core.getImage()
        self.set_data(last)

    def _on_streaming_start(self) -> None:
        if (core := self._mmc) is not None:
            wait = int(core.getExposure()) or _DEFAULT_WAIT
            self._timer_id = self.startTimer(wait, Qt.TimerType.PreciseTimer)

    def _on_streaming_stop(self) -> None:
        if self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = None

    def _on_system_config_loaded(self) -> None:
        pass

    def _on_roi_set(self) -> None:
        pass

    def _on_property_changed(self, dev: str, prop: str, value: str) -> None:
        pass
