"""Defines actions that toggle/create singleton widgets."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Annotated, TypeVar, cast

import pymmcore_widgets as pmmw
from pymmcore_plus import CMMCorePlus
from useq import AcquireImage, HardwareAutofocus, MDAEvent, MDASequence

from pymmcore_gui._qt.QtAds import CDockWidget, DockWidgetArea, SideBarLocation
from pymmcore_gui._qt.QtCore import Qt, Signal
from pymmcore_gui._qt.QtGui import QAction
from pymmcore_gui._qt.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget

from ._action_info import ActionKey, WidgetActionInfo, _ensure_isinstance

if TYPE_CHECKING:
    from pathlib import Path

    from pymmcore_gui._main_window import MicroManagerGUI
    from pymmcore_gui._qt.QtCore import QObject
    from pymmcore_gui.widgets._exception_log import ExceptionLog
    from pymmcore_gui.widgets._mm_console import MMConsole
    from pymmcore_gui.widgets._stage_control import StagesControlWidget

QWidgetType = Annotated[QWidget, _ensure_isinstance(QWidget)]

CT = TypeVar("CT", bound=Callable[[QWidget], QWidget])


class WidgetAction(ActionKey):
    """Widget Actions toggle/create singleton widgets."""

    ABOUT = "pymmcore_gui.about_widget"
    PROP_BROWSER = "pymmcore_gui.property_browser"
    PIXEL_CONFIG = "pymmcore_gui.pixel_config_widget"
    INSTALL_DEVICES = "pymmcore_gui.install_devices_widget"
    MDA_WIDGET = "pymmcore_gui.mda_widget"
    CONFIG_GROUPS = "pymmcore_gui.config_groups_widget"
    CAMERA_ROI = "pymmcore_gui.camera_roi_widget"
    CONSOLE = "pymmcore_gui.console"
    EXCEPTION_LOG = "pymmcore_gui.exception_log"
    STAGE_CONTROL = "pymmcore_gui.stage_control_widget"
    STAGE_EXPLORER = "pymmcore_gui.stage_explorer_widget"
    CONFIG_WIZARD = "pymmcore_gui.hardware_config_wizard"


# ######################## Functions that create widgets #########################


def _get_mm_main_window(obj: QObject) -> MicroManagerGUI | None:
    if obj.objectName() == "MicroManagerGUI":
        return cast("MicroManagerGUI", obj)
    parent = obj.parent()
    while parent is not None:
        if parent.objectName() == "MicroManagerGUI":
            return cast("MicroManagerGUI", parent)
        parent = parent.parent()
    return None


def _get_core(obj: QObject) -> CMMCorePlus:
    if win := _get_mm_main_window(obj):
        return win.mmcore
    return CMMCorePlus.instance()


def create_property_browser(parent: QWidget) -> pmmw.PropertyBrowser:
    """Create a Property Browser widget."""
    from pymmcore_widgets import PropertyBrowser

    return PropertyBrowser(parent=parent, mmcore=_get_core(parent))


def create_mm_console(parent: QWidget) -> MMConsole:
    """Create a console widget."""
    from pymmcore_gui.widgets._mm_console import MMConsole

    return MMConsole(parent=parent)


def create_install_widgets(parent: QWidget) -> QDialog:
    """Create the Install Devices widget."""
    from pymmcore_widgets import InstallWidget

    class InstallDialog(QDialog):
        def __init__(self, parent: QWidget | None = None):
            super().__init__(parent)
            self._install_widget = InstallWidget(parent=self)

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self._install_widget)

    wdg = InstallDialog(parent=parent)
    wdg.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window)
    wdg.resize(800, 400)
    return wdg


def create_mda_widget(parent: QWidget) -> pmmw.MDAWidget:
    """Create the MDA widget."""

    class MDAWidget(pmmw.MDAWidget):
        """MDAWidget subclass: defaults to in-memory output and hides tiff-sequence."""

        statusRequested = Signal(str)

        def __init__(
            self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
        ) -> None:
            super().__init__(parent=parent, mmcore=mmcore)
            self._hide_tiff_sequence()
            self._active_sequence: MDASequence | None = None
            self._frame_total = 0
            self._frame_index = 0
            self._last_event: MDAEvent | None = None
            self._is_paused = False
            self._was_canceled = False

            self._status_label = QLabel("Idle", self)
            self._status_label.setObjectName("mdaStatusLabel")
            self._status_label.setWordWrap(True)
            self._status_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            self.statusRequested.connect(self._status_label.setText)

            layout = cast("QVBoxLayout", self.layout())
            layout.addWidget(self._status_label)

            events = self._mmc.mda.events
            events.sequenceStarted.connect(self._on_sequence_started)
            events.eventStarted.connect(self._on_event_started)
            events.frameReady.connect(self._on_frame_ready)
            events.awaitingEvent.connect(self._on_awaiting_event)
            events.sequencePauseToggled.connect(self._on_pause_toggled)
            events.sequenceCanceled.connect(self._on_sequence_canceled)
            events.sequenceFinished.connect(self._on_sequence_finished)

        def _hide_tiff_sequence(self) -> None:
            """Remove the 'tiff-sequence' option from the save widget's writer combo."""
            combo = self.save_info._writer_combo
            for i in range(combo.count()):
                if combo.itemText(i) == "tiff-sequence":
                    combo.removeItem(i)
                    break

        def prepare_mda(self) -> bool | str | Path | None:
            output = super().prepare_mda()
            if output is None:
                output = "memory"
            return output

        def _axis_value(self, event: MDAEvent | None, axis: str) -> int | None:
            if event is None:
                return None
            for key, value in event.index.items():
                if str(key) == axis:
                    return int(value) + 1
            return None

        def _axis_total(self, axis: str) -> int | None:
            if self._active_sequence is None:
                return None
            for key, value in self._active_sequence.sizes.items():
                if str(key) == axis and value:
                    return int(value)
            return None

        def _channel_name(self, event: MDAEvent | None) -> str | None:
            if event is None or event.channel is None:
                return None
            return event.channel.config or None

        def _event_produces_frame(self, event: MDAEvent) -> bool:
            action = getattr(event, "action", None)
            return action is None or isinstance(action, AcquireImage)

        def _count_expected_frames(self, sequence: MDASequence) -> int:
            return sum(
                1
                for event in sequence.iter_events()
                if self._event_produces_frame(event)
            )

        def _format_status(
            self,
            *,
            step: str,
            event: MDAEvent | None = None,
            next_seconds: float | None = None,
        ) -> str:
            current_event = event or self._last_event
            parts = [f"Frame {self._frame_index}/{self._frame_total}"]

            for axis, label in (("p", "Pos"), ("t", "T"), ("z", "Z")):
                value = self._axis_value(current_event, axis)
                total = self._axis_total(axis)
                if value is not None and total:
                    parts.append(f"{label} {value}/{total}")

            if channel := self._channel_name(current_event):
                parts.append(f"Channel {channel}")

            parts.append(f"Step: {step}")

            if next_seconds is not None:
                parts.append(f"Next: {next_seconds:.1f} s")

            return " | ".join(parts)

        def _set_status(
            self,
            *,
            step: str,
            event: MDAEvent | None = None,
            next_seconds: float | None = None,
        ) -> None:
            self.statusRequested.emit(
                self._format_status(step=step, event=event, next_seconds=next_seconds)
            )

        def _on_sequence_started(
            self, sequence: MDASequence, meta: Mapping[str, object]
        ) -> None:
            self._active_sequence = sequence
            self._frame_total = self._count_expected_frames(sequence)
            self._frame_index = 0
            self._last_event = None
            self._is_paused = False
            self._was_canceled = False
            self._set_status(step="Preparing")

        def _on_event_started(self, event: MDAEvent) -> None:
            self._last_event = event
            action = getattr(event, "action", None)
            if isinstance(action, HardwareAutofocus):
                self._set_status(step="Autofocus", event=event)
            else:
                self._set_status(step="Acquiring", event=event)

        def _on_frame_ready(
            self, image: object, event: MDAEvent, meta: Mapping[str, object]
        ) -> None:
            self._last_event = event
            self._frame_index += 1
            self._set_status(step="Acquiring", event=event)

        def _on_awaiting_event(self, event: MDAEvent, remaining_sec: float) -> None:
            self._last_event = event
            step = "Paused" if self._is_paused else "Waiting next frame"
            self._set_status(step=step, event=event, next_seconds=remaining_sec)

        def _on_pause_toggled(self, paused: bool) -> None:
            self._is_paused = paused
            step = "Paused" if paused else "Waiting next frame"
            self._set_status(step=step)

        def _on_sequence_canceled(self, sequence: MDASequence) -> None:
            self._was_canceled = True
            self._set_status(step="Canceled")

        def _on_sequence_finished(self, sequence: MDASequence) -> None:
            finish_reason = getattr(self._mmc.mda.status, "finish_reason", None)
            if finish_reason is not None and str(finish_reason) == "errored":
                step = "Error"
            else:
                step = "Canceled" if self._was_canceled else "Finished"
            self._set_status(step=step)

    return MDAWidget(parent=parent, mmcore=_get_core(parent))


def create_camera_roi(parent: QWidget) -> pmmw.CameraRoiWidget:
    """Create the Camera ROI widget."""
    from pymmcore_widgets import CameraRoiWidget

    return CameraRoiWidget(parent=parent, mmcore=_get_core(parent))


def create_config_groups(parent: QWidget) -> pmmw.GroupPresetTableWidget:
    """Create the Config Groups widget."""
    from pymmcore_widgets import GroupPresetTableWidget

    return GroupPresetTableWidget(parent=parent, mmcore=_get_core(parent))


def create_pixel_config(parent: QWidget) -> pmmw.PixelConfigurationWidget:
    """Create the Pixel Configuration widget."""
    from pymmcore_gui._qt.QtAds import CDockWidget

    class PixelConfigurationWidget(pmmw.PixelConfigurationWidget):
        def close(self) -> bool:
            # Hide the parent CDockWidget container instead of closing this widget,
            # so the widget is preserved and can be reopened. Qt-ADS may nest this
            # widget inside intermediate containers (e.g. a scroll area or wrapper
            # widget) before the CDockWidget ancestor, so we need to walk up the parent
            # chain to find it
            parent = self.parent()
            while parent is not None:
                if isinstance(parent, CDockWidget):
                    parent.toggleView(False)
                    return True
                parent = parent.parent()
            return super().close()

    return PixelConfigurationWidget(parent=parent, mmcore=_get_core(parent))


def create_exception_log(parent: QWidget) -> ExceptionLog:
    """Create the Exception Log widget."""
    from pymmcore_gui.widgets._exception_log import ExceptionLog

    wdg = ExceptionLog(parent=parent)
    wdg.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window)
    wdg.resize(800, 400)
    return wdg


def create_stage_widget(parent: QWidget) -> StagesControlWidget:
    """Create the Stage Control widget."""
    from pymmcore_gui.widgets._stage_control import StagesControlWidget

    return StagesControlWidget(parent=parent, mmcore=_get_core(parent))


def create_config_wizard(parent: QWidget) -> pmmw.ConfigWizard:
    """Create the Hardware Configuration Wizard."""
    from pymmcore_widgets import ConfigWizard

    mmcore = _get_core(parent)
    config_file = mmcore.systemConfigurationFile() or ""
    return ConfigWizard(config_file=config_file, core=mmcore, parent=parent)


def create_stage_explorer_widget(parent: QWidget) -> pmmw.StageExplorer:
    """Create the Stage Explorer widget."""
    from pymmcore_widgets import StageExplorer

    return StageExplorer(parent=parent, mmcore=_get_core(parent))


# ######################## WidgetAction Enum #########################


# ######################## WidgetActionInfos #########################


def create_about_widget(parent: QWidget) -> QWidget:
    """Create an "about this program" widget."""
    from pymmcore_gui.widgets._about_widget import AboutWidget

    return AboutWidget(parent=parent)


show_about = WidgetActionInfo(
    key=WidgetAction.ABOUT,
    text="About Pymmcore Gui...",
    create_widget=create_about_widget,
    dock_area=None,
    checkable=False,
    menu_role=QAction.MenuRole.AboutRole,
    scroll_mode=CDockWidget.eInsertMode.ForceNoScrollArea,
)

show_console = WidgetActionInfo(
    key=WidgetAction.CONSOLE,
    text="Console",
    shortcut="Ctrl+Shift+C",
    icon="iconoir:terminal",
    create_widget=create_mm_console,
    dock_area=DockWidgetArea.BottomDockWidgetArea,
)

show_property_browser = WidgetActionInfo(
    key=WidgetAction.PROP_BROWSER,
    text="Device Property Browser...",
    shortcut="Ctrl+Shift+P",
    icon="mdi-light:format-list-bulleted",
    create_widget=create_property_browser,
    dock_area=SideBarLocation.SideBarLeft,
)

show_install_devices = WidgetActionInfo(
    key=WidgetAction.INSTALL_DEVICES,
    text="Install Devices...",
    shortcut="Ctrl+Shift+I",
    icon="mdi-light:download",
    create_widget=create_install_widgets,
    dock_area=None,
    checkable=False,
    scroll_mode=CDockWidget.eInsertMode.ForceNoScrollArea,
)

show_mda_widget = WidgetActionInfo(
    key=WidgetAction.MDA_WIDGET,
    text="MDA",
    shortcut="Ctrl+Shift+M",
    icon="qlementine-icons:cube-16",
    create_widget=create_mda_widget,
)

show_camera_roi = WidgetActionInfo(
    key=WidgetAction.CAMERA_ROI,
    text="Camera ROI",
    shortcut="Ctrl+Shift+R",
    icon="material-symbols-light:screenshot-region-rounded",
    create_widget=create_camera_roi,
    dock_area=DockWidgetArea.LeftDockWidgetArea,
)

show_config_groups = WidgetActionInfo(
    key=WidgetAction.CONFIG_GROUPS,
    text="Config Groups",
    shortcut="Ctrl+Shift+G",
    icon="mdi-light:format-list-bulleted",
    create_widget=create_config_groups,
    dock_area=DockWidgetArea.LeftDockWidgetArea,
    scroll_mode=CDockWidget.eInsertMode.ForceNoScrollArea,
)

show_pixel_config = WidgetActionInfo(
    key=WidgetAction.PIXEL_CONFIG,
    text="Pixel Size Configuration",
    shortcut="Ctrl+Shift+X",
    icon="mdi-light:grid",
    create_widget=create_pixel_config,
)

show_exception_log = WidgetActionInfo(
    key=WidgetAction.EXCEPTION_LOG,
    text="Exception Log",
    shortcut="Ctrl+Shift+E",
    icon="mdi-light:alert",
    create_widget=create_exception_log,
    dock_area=None,
)

show_stage_control = WidgetActionInfo(
    key=WidgetAction.STAGE_CONTROL,
    text="Stage Control",
    shortcut="Ctrl+Shift+S",
    icon="fa:arrows",
    create_widget=create_stage_widget,
    dock_area=DockWidgetArea.LeftDockWidgetArea,
)

show_config_wizard = WidgetActionInfo(
    key=WidgetAction.CONFIG_WIZARD,
    text="Hardware Config Wizard...",
    icon="mdi:cog",
    create_widget=create_config_wizard,
    dock_area=None,
    checkable=False,
)

stage_explorer_widget = WidgetActionInfo(
    key=WidgetAction.STAGE_EXPLORER,
    text="Stage Explorer",
    icon="mdi:map-search",
    create_widget=create_stage_explorer_widget,
    dock_area=DockWidgetArea.LeftDockWidgetArea,
    floatable=False,
)
