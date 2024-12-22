from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from pymmcore_plus import CMMCorePlus
from PyQt6.QtCore import Qt

from pymmcore_gui.actions._action_info import ActionKey

from ._action_info import ActionInfo

if TYPE_CHECKING:
    from collections.abc import Callable

    from pymmcore_widgets import PropertyBrowser
    from PyQt6.QtCore import QObject
    from PyQt6.QtWidgets import QWidget

    from pymmcore_gui._main_window import MicroManagerGUI
    from pymmcore_gui.widgets._mm_console import MMConsole


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
        return win.mmc
    return CMMCorePlus.instance()


def create_property_browser(parent: QWidget) -> PropertyBrowser:
    """Create a Property Browser widget."""
    from pymmcore_widgets import PropertyBrowser

    mmc = _get_core(parent)
    wdg = PropertyBrowser(parent=parent, mmcore=mmc)
    wdg.show()
    return wdg


def create_mm_console(parent: QWidget) -> MMConsole:
    """Create a console widget."""
    from pymmcore_gui.widgets._mm_console import MMConsole

    return MMConsole(parent=parent)


# ######################## WidgetAction Enum #########################


class WidgetAction(ActionKey):
    """Widget Actions toggle/create singleton widgets."""

    PROP_BROWSER = "Property Browser"
    PIXEL_CONFIG = "Pixel Configuration"
    INSTALL_DEVICES = "Install Devices"
    MDA_WIDGET = "MDA Widget"
    CONFIG_GROUPS = "Config Groups"
    CAMERA_ROI = "Camera ROI"
    CONSOLE = "Console"

    def create_widget(self, parent: QWidget) -> QWidget:
        """Create the widget associated with this action."""
        if self not in _CREATOR_MAP:  # pragma: no cover
            raise NotImplementedError(f"No constructor has been provided for {self!r}")
        return _CREATOR_MAP[self](parent)

    def dock_area(self) -> Qt.DockWidgetArea | None:
        """Return the default dock area for this widget."""
        return _DOCK_AREAS.get(self, Qt.DockWidgetArea.RightDockWidgetArea)


_CREATOR_MAP: dict[WidgetAction, Callable[[QWidget], QWidget]] = {
    WidgetAction.CONSOLE: create_mm_console,
    WidgetAction.PROP_BROWSER: create_property_browser,
}

# preferred area for each widget.  If None, no dock widget is set.
_DOCK_AREAS: dict[WidgetAction, Qt.DockWidgetArea | None] = {
    WidgetAction.CONSOLE: Qt.DockWidgetArea.BottomDockWidgetArea,
    WidgetAction.PROP_BROWSER: None,
}

# ######################## WidgetActionInfos #########################


@dataclass
class WidgetActionInfo(ActionInfo):
    """Subclass to set default values for WidgetAction."""

    checkable: bool = True


show_console = WidgetActionInfo(
    key=WidgetAction.CONSOLE,
    shortcut="Ctrl+Shift+C",
    icon="iconoir:terminal",
)

show_property_browser = WidgetActionInfo(
    key=WidgetAction.PROP_BROWSER,
    shortcut="Ctrl+Shift+P",
    icon="mdi-light:format-list-bulleted",
)
