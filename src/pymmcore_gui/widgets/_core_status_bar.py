from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING

from pymmcore_widgets.control._q_stage_controller import QStageMoveAccumulator

from pymmcore_gui._qt.QtCore import QTimer
from pymmcore_gui._qt.QtGui import QPalette
from pymmcore_gui._qt.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from useq import MDASequence


class CoreStatusBar(QWidget):
    """Status bar widget showing core state: position, channel, camera, MDA."""

    def __init__(self, mmcore: CMMCorePlus, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mmc = mmcore

        pal = self.palette()
        pal.setColor(
            QPalette.ColorRole.WindowText,
            pal.color(QPalette.ColorRole.PlaceholderText),
        )
        self.setPalette(pal)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._xy_accum: QStageMoveAccumulator | None = None

        self._xy_label = QLabel()
        self._z_label = QLabel()
        self._channel_label = QLabel()
        self._camera_label = QLabel()

        self._mda_label = QLabel("MDA: idle")
        self._mda_progress = QProgressBar()
        self._mda_progress.setFixedHeight(14)
        self._mda_progress.setFixedWidth(240)
        self._mda_progress.setTextVisible(True)
        self._mda_progress.setMaximum(1)
        self._mda_progress.setValue(0)
        self._mda_total = 0
        self._mda_count = 0
        self._mda_progress.hide()

        self._mda_hide_timer = QTimer(self)
        self._mda_hide_timer.setSingleShot(True)
        self._mda_hide_timer.setInterval(5000)
        self._mda_hide_timer.timeout.connect(self._hide_mda_progress)

        sep_style = "color: palette(mid);"
        labels: list[QWidget] = [
            self._xy_label,
            self._z_label,
            self._channel_label,
            self._camera_label,
        ]
        for i, widget in enumerate(labels):
            if i > 0:
                sep = QLabel("|")
                sep.setStyleSheet(sep_style)
                layout.addWidget(sep)
            layout.addWidget(widget)

        layout.addStretch()
        layout.addWidget(self._mda_label)
        layout.addWidget(self._mda_progress)

        # Initialize display
        self._update_xy_position()
        self._update_z_position()
        self._update_channel()
        self._update_camera_info()

        # Connect signals
        ev = self._mmc.events
        ev.stagePositionChanged.connect(self._on_z_changed)
        ev.configSet.connect(self._on_config_set)
        ev.channelGroupChanged.connect(self._on_channel_group_changed)
        ev.systemConfigurationLoaded.connect(self._on_system_loaded)
        ev.propertyChanged.connect(self._on_property_changed)
        ev.roiSet.connect(self._on_roi_set)

        self._setup_xy_accumulator()

        mda_ev = self._mmc.mda.events
        mda_ev.sequenceStarted.connect(self._on_mda_started)
        mda_ev.frameReady.connect(self._on_mda_frame)
        mda_ev.sequenceFinished.connect(self._on_mda_finished)
        mda_ev.sequenceCanceled.connect(self._on_mda_finished)

    # ---- accumulator setup ----

    def _setup_xy_accumulator(self) -> None:
        self._disconnect_xy_accumulator()
        xy_dev = self._mmc.getXYStageDevice()
        if xy_dev:
            with suppress(Exception):
                accum = QStageMoveAccumulator.for_device(xy_dev, self._mmc)
                accum.moveFinished.connect(self._update_xy_position)
                self._xy_accum = accum

    def _disconnect_xy_accumulator(self) -> None:
        if self._xy_accum is not None:
            with suppress(TypeError, RuntimeError):
                self._xy_accum.moveFinished.disconnect(self._update_xy_position)
            self._xy_accum = None

    # ---- update helpers ----

    def _update_xy_position(self) -> None:
        if not self._mmc.getXYStageDevice():
            self._xy_label.setText("XY: --")
            return
        x = self._mmc.getXPosition()
        y = self._mmc.getYPosition()
        self._xy_label.setText(f"XY: {x:.1f}, {y:.1f}")

    def _update_z_position(self, z: float | None = None) -> None:
        if not self._mmc.getFocusDevice():
            self._z_label.setText("Z: --")
            return
        if z is None:
            z = self._mmc.getPosition()
        self._z_label.setText(f"Z: {z:.1f}")

    def _update_channel(self) -> None:
        group = self._mmc.getChannelGroup()
        if group:
            config = self._mmc.getCurrentConfig(group)
            self._channel_label.setText(f"Ch: {config}" if config else "Ch: --")
        else:
            self._channel_label.setText("Ch: --")

    def _update_camera_info(self) -> None:
        if not self._mmc.getCameraDevice():
            self._camera_label.setText("Cam: --")
            return
        w = self._mmc.getImageWidth()
        h = self._mmc.getImageHeight()
        bits = self._mmc.getImageBitDepth()
        cam = self._mmc.getCameraDevice()
        binning = self._mmc.getProperty(cam, "Binning")
        self._camera_label.setText(f"{w}x{h} bin:{binning} {bits}bit")

    def _hide_mda_progress(self) -> None:
        self._mda_progress.hide()
        self._mda_progress.setMaximum(1)
        self._mda_progress.setValue(0)
        self._mda_label.setText("MDA: idle")

    # ---- signal callbacks ----

    def _on_z_changed(self, dev: str, z: float) -> None:
        if dev == self._mmc.getFocusDevice():
            self._update_z_position(z)

    def _on_config_set(self, group: str, _config: str) -> None:
        if group == self._mmc.getChannelGroup():
            self._update_channel()

    def _on_channel_group_changed(self, *_args: object) -> None:
        self._update_channel()

    def _on_system_loaded(self) -> None:
        self._setup_xy_accumulator()
        self._update_xy_position()
        self._update_z_position()
        self._update_channel()
        self._update_camera_info()

    def _on_property_changed(self, dev: str, prop: str, _val: str) -> None:
        cam = self._mmc.getCameraDevice()
        if dev == cam and prop == "Binning":
            self._update_camera_info()

    def _on_roi_set(self, *_args: object) -> None:
        self._update_camera_info()

    def _on_mda_started(self, sequence: MDASequence, *_args: object) -> None:
        self._mda_hide_timer.stop()
        self._mda_total = len(list(sequence))
        self._mda_count = 0
        self._mda_progress.setMaximum(self._mda_total)
        self._mda_progress.setValue(0)
        self._mda_progress.setFormat("%v/%m")
        self._mda_label.setText("MDA:")
        self._mda_progress.show()

    def _on_mda_frame(self, *_args: object) -> None:
        self._mda_count += 1
        self._mda_progress.setValue(self._mda_count)

    def _on_mda_finished(self, *_args: object) -> None:
        self._mda_progress.setValue(self._mda_progress.maximum())
        self._mda_label.setText("MDA: done")
        self._mda_hide_timer.start()

    def setVisible(self, visible: bool) -> None:
        super().setVisible(visible)
        if visible:
            self._update_xy_position()
            self._update_z_position()
            self._update_channel()
            self._update_camera_info()
