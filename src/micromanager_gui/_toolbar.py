from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, Any, cast

from fonticon_mdi6 import MDI6
from pymmcore_widgets import MDAWidget, PropertyBrowser
from qtpy.QtCore import QByteArray, QSize, Qt
from qtpy.QtWidgets import (
    QDockWidget,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolBar,
    QWidget,
)
from superqt.fonticon import icon

from micromanager_gui._util import (
    USER_DIR,
    USER_LAYOUT_PATH,
)

from ._widgets._camera_roi import _CameraRoiWidget
from ._widgets._group_and_preset import _GroupsAndPresets
from ._widgets._pixel_configurations import _PixelConfigurationWidget
from ._widgets._shutters_toolbar import _ShuttersToolbar
from ._widgets._snap_and_live import Live, Snap
from ._widgets._stage_control import _StagesControlWidget

if TYPE_CHECKING:
    from ._main_window import MicroManagerGUI


BTN_SIZE = (60, 40)
ALLOWED_AREAS = (
    Qt.DockWidgetArea.LeftDockWidgetArea
    | Qt.DockWidgetArea.RightDockWidgetArea
    # | Qt.DockWidgetArea.BottomDockWidgetArea
)


# fmt: off
# key: (widget, window name, icon)
WIDGETS: dict[str, tuple[type[QWidget], str, str | None]] = {
    "Shutters": (_ShuttersToolbar, "Shutters Control", MDI6.hexagon_slice_6),
    "Camera ROI": (_CameraRoiWidget, "Camera ROI", MDI6.crop),
    "Property Browser": (PropertyBrowser, "Device Property Browser", MDI6.table_large),
    "Group Presets": (_GroupsAndPresets, "Group & Presets Table", MDI6.table_large_plus),  # noqa: E501
    "Stages": (_StagesControlWidget, "Stages Control", MDI6.arrow_all),
    "Pixel": (_PixelConfigurationWidget, "Pixel Configuration Table", None),
    "MDA": (MDAWidget, "Multi-Dimensional Acquisition", None),
}
# fmt: on


class ScrollableDockWidget(QDockWidget):
    """A QDockWidget with a QScrollArea."""

    def __init__(
        self,
        title: str,
        parent: QWidget | None = None,
        *,
        widget: QWidget,
        objectName: str,
    ):
        super().__init__(title, parent)
        # set the object name
        self.setObjectName(objectName)

        # set allowed dock areas
        self.setAllowedAreas(ALLOWED_AREAS)

        # create the scroll area and set it as the widget of the QDockwidget
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        super().setWidget(self.scroll_area)

        # set the widget to the scroll area
        self.scroll_area.setWidget(widget)
        # resize the dock widget to the size hint of the widget
        self.resize(widget.minimumSizeHint())


class MainToolBar(QToolBar):
    """A QToolBar containing QPushButtons for pymmcore-widgets."""

    def __init__(self, parent: MicroManagerGUI) -> None:
        super().__init__(parent)

        self._main_window = parent

        self.setAllowedAreas(Qt.ToolBarArea.AllToolBarAreas)

        # snap and live toolbar
        self._snap_live_toolbar = SnapLiveToolBar(self)
        self._main_window.addToolBar(
            Qt.ToolBarArea.TopToolBarArea, self._snap_live_toolbar
        )

        # widgets toolbar
        self._widgets_toolbar = _WidgetsToolBar(
            self, main_window=self._main_window, main_toolbar=self
        )
        self._main_window.addToolBar(
            Qt.ToolBarArea.TopToolBarArea, self._widgets_toolbar
        )

        # shutters toolbar
        self._shutter_toolbar = _ShuttersToolbar(self)
        self._main_window.addToolBar(
            Qt.ToolBarArea.TopToolBarArea, self._shutter_toolbar
        )

    def contextMenuEvent(self, event: Any) -> None:
        """Remove all actions from the context menu but the shutter toolbar."""
        menu = self._main_window.createPopupMenu()
        for action in menu.actions():
            if action.text() == "Shutters ToolBar":
                continue
            menu.removeAction(action)
        menu.exec_(event.globalPos())


class SnapLiveToolBar(QToolBar):
    """A QToolBar containing QPushButtons for snap and live."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Snap/Live Toolbar", parent)

        self.setObjectName("Snap/Live ToolBar")

        self.setAllowedAreas(Qt.ToolBarArea.AllToolBarAreas)

        self._snap_button = Snap()
        self._live_button = Live()

        self.addWidget(self._snap_button)
        self.addWidget(self._live_button)


class _WidgetsToolBar(QToolBar):
    """A QToolBar containing QPushButtons for pymmcore-widgets.

    e.g. Property Browser, MDAWidget, StagesWidget, ...

    The QPushButton.whatsThis() property is used to store the key that
    will be used by the `_show_widget` method.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        main_window: MicroManagerGUI,
        main_toolbar: MainToolBar,
    ) -> None:
        super().__init__("Widgets ToolBar", parent)

        self.setObjectName("Widgets ToolBar")

        self.setAllowedAreas(Qt.ToolBarArea.AllToolBarAreas)

        self._main_window = main_window
        self._main_toolbar = main_toolbar

        # keep track of the created widgets
        self._widgets: dict[str, ScrollableDockWidget] = {}

        for key in WIDGETS:
            _, windows_name, btn_icon = WIDGETS[key]
            btn = QPushButton()
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.setToolTip(windows_name)
            btn.setWhatsThis(key)
            btn.setIcon(icon(btn_icon)) if btn_icon else btn.setText(key)
            btn.setFixedSize(*BTN_SIZE)
            btn.setIconSize(QSize(25, 25))
            if key == "Shutters":
                btn.clicked.connect(self._show_shutters_toolbar)
            else:
                btn.clicked.connect(self._show_widget)
            self.addWidget(btn)

    def _show_shutters_toolbar(self) -> None:
        """Show or raise the shutters toolbar."""
        if self._main_toolbar._shutter_toolbar is None:
            return
        if self._main_toolbar._shutter_toolbar.isVisible():
            self._main_toolbar._shutter_toolbar.hide()
        else:
            self._main_toolbar._shutter_toolbar.show()

    def _show_widget(self, key: str = "") -> None:
        """Show or raise a widget."""
        if not key:
            # using QPushButton.whatsThis() property to get the key.
            btn = cast(QPushButton, self.sender())
            key = btn.whatsThis()

        if key in self._widgets:
            # already exists
            wdg = self._widgets[key]
            wdg.show()
            wdg.raise_()
            return

        wdg = self._create_widget(key)
        wdg.show()

    def _create_widget(self, key: str) -> ScrollableDockWidget:
        """Create a widget for the first time."""
        try:
            wdg_cls = WIDGETS[key][0]
        except KeyError as e:
            raise KeyError(
                "Not a recognized widget key. "
                f"Must be one of {list(WIDGETS)} "
                " or the `whatsThis` property of a `sender` `QPushButton`."
            ) from e

        wdg = wdg_cls(parent=self, mmcore=self._main_window._mmc)

        windows_title = WIDGETS[key][1]
        dock = ScrollableDockWidget(windows_title, self, widget=wdg, objectName=key)
        self._connect_dock_widget(dock)
        self._main_window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.setFloating(True)
        self._widgets[key] = dock

        return dock

    def _connect_dock_widget(self, dock_wdg: QDockWidget) -> None:
        """Connect the dock widget to the main window."""
        dock_wdg.visibilityChanged.connect(self._save_layout)
        dock_wdg.topLevelChanged.connect(self._save_layout)
        dock_wdg.dockLocationChanged.connect(self._save_layout)

    def _save_layout(self) -> None:
        """Save the napa-micromanager layout to a json file.

        The json file has two keys:
        - "layout_state" where the state of napari main window is stored using the
          saveState() method. The state is base64 encoded to be able to save it to the
          json file.
        - "pymmcore_widgets" where the names of the docked pymmcore_widgets are stored.

        IMPORTANT: The "pymmcore_widgets" key is crucial in our layout saving process.
        It stores the names of all active pymmcore_widgets at the time of saving. Before
        restoring the layout, we must recreate these widgets. If not, they won't be
        included in the restored layout.
        """
        # get the names of the pymmcore_widgets that are part of the layout
        pymmcore_wdgs: list[str] = []
        for dock_wdg in self._main_window.findChildren(ScrollableDockWidget):
            wdg_name = dock_wdg.objectName()
            if wdg_name in WIDGETS:
                pymmcore_wdgs.append(wdg_name)

        # get the state of the napari main window as bytes
        state_bytes = self._main_window.saveState().data()

        # Create dictionary with widget names and layout state. The layout state is
        # base64 encoded to be able to save it to a json file.
        data = {
            "pymmcore_widgets": pymmcore_wdgs,
            "layout_state": base64.b64encode(state_bytes).decode(),
        }

        # if the user layout path does not exist, create it
        if not USER_LAYOUT_PATH.exists():
            USER_DIR.mkdir(parents=True, exist_ok=True)

        try:
            with open(USER_LAYOUT_PATH, "w") as json_file:
                json.dump(data, json_file)
        except Exception as e:
            print(f"Was not able to save layout to file. Error: {e}")

    def _load_layout(self) -> None:
        """Load the napari-micromanager layout from a json file."""
        if not USER_LAYOUT_PATH.exists():
            return

        try:
            with open(USER_LAYOUT_PATH) as f:
                data = json.load(f)

                # get the layout state bytes
                state_bytes = data.get("layout_state")

                if state_bytes is None:
                    return

                # add pymmcore_widgets to the main window
                pymmcore_wdgs = data.get("pymmcore_widgets", [])
                for wdg_name in pymmcore_wdgs:
                    if wdg_name in WIDGETS:
                        self._show_widget(wdg_name)

                # Convert base64 encoded string back to bytes
                state_bytes = base64.b64decode(state_bytes)

                # restore the layout state
                self._main_window.restoreState(QByteArray(state_bytes))

        except Exception as e:
            print(f"Was not able to load layout from file. Error: {e}")
