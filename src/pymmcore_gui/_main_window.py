from __future__ import annotations

import warnings
from collections import ChainMap
from enum import Enum
from typing import TYPE_CHECKING, cast
from weakref import WeakValueDictionary

import ndv
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda.handlers import TensorStoreHandler
from pymmcore_widgets import ImagePreview
from PyQt6.QtCore import QObject, Qt, QTimer
from PyQt6.QtGui import QAction, QCloseEvent
from PyQt6.QtWidgets import (
    QDialog,
    QDockWidget,
    QMainWindow,
    QMenu,
    QMenuBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pymmcore_gui.actions._core_qaction import QCoreAction
from pymmcore_gui.actions.widget_actions import WidgetActionInfo

from .actions import CoreAction, WidgetAction
from .actions._action_info import ActionKey
from .widgets._toolbars import OCToolBar, ShuttersToolbar

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    import numpy as np
    import useq
    from pymmcore_plus.mda import SupportsFrameReady
    from pymmcore_plus.metadata import FrameMetaV1, SummaryMetaV1
    from useq import MDASequence


class Menu(str, Enum):
    """Menu names."""

    PYMM_GUI = "pymmcore-gui"
    WINDOW = "Window"

    def __str__(self) -> str:
        return str(self.value)


class Toolbar(str, Enum):
    """Toolbar names."""

    CAMERA_ACTIONS = "Camera Actions"
    OPTICAL_CONFIGS = "Optical Configs"
    WIDGETS = "Widgets"
    SHUTTERS = "Shutters"

    def __str__(self) -> str:
        return str(self.value)


class MicroManagerGUI(QMainWindow):
    """Micro-Manager minimal GUI."""

    # Toolbars are a mapping of strings to either a list of ActionKeys or a callable
    # that takes a CMMCorePlus instance and QMainWindow and returns a QToolBar.
    TOOLBARS: Mapping[
        str, list[ActionKey] | Callable[[CMMCorePlus, QMainWindow], QToolBar]
    ] = {
        Toolbar.CAMERA_ACTIONS: [
            CoreAction.SNAP,
            CoreAction.TOGGLE_LIVE,
        ],
        Toolbar.OPTICAL_CONFIGS: OCToolBar,
        Toolbar.SHUTTERS: ShuttersToolbar,
        Toolbar.WIDGETS: [
            WidgetAction.CONSOLE,
            WidgetAction.PROP_BROWSER,
            WidgetAction.MDA_WIDGET,
            WidgetAction.STAGE_CONTROL,
            WidgetAction.CAMERA_ROI,
        ],
    }
    # Menus are a mapping of strings to either a list of ActionKeys or a callable
    # that takes a CMMCorePlus instance and QMainWindow and returns a QMenu.
    MENUS: Mapping[
        str, list[ActionKey] | Callable[[CMMCorePlus, QMainWindow], QMenu]
    ] = {
        Menu.PYMM_GUI: [WidgetAction.ABOUT],
        Menu.WINDOW: [
            WidgetAction.CONSOLE,
            WidgetAction.PROP_BROWSER,
            WidgetAction.INSTALL_DEVICES,
            WidgetAction.MDA_WIDGET,
            WidgetAction.STAGE_CONTROL,
            WidgetAction.CAMERA_ROI,
            WidgetAction.CONFIG_GROUPS,
            WidgetAction.EXCEPTION_LOG,
            WidgetAction.CONFIG_WIZARD,
        ],
    }

    def __init__(self, *, mmcore: CMMCorePlus | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Mike")
        self.setObjectName("MicroManagerGUI")

        # Serves to cache created QAction objects so that they can be re-used
        # when the same action is requested multiple times. This is useful to
        # synchronize the state of actions that may appear in multiple menus or
        # toolbars.
        self._qactions = WeakValueDictionary[ActionKey, QAction]()
        self._inner_widgets = WeakValueDictionary[ActionKey, QWidget]()
        self._dock_widgets = WeakValueDictionary[ActionKey, QDockWidget]()
        self._qwidgets = ChainMap[ActionKey, QWidget](
            self._dock_widgets,  # type: ignore [arg-type]  # (not covariant)
            self._inner_widgets,
        )

        # get global CMMCorePlus instance
        self._mmc = mmc = mmcore or CMMCorePlus.instance()

        self._viewers_manager = _ViewersManager(self, self._mmc)

        # MENUS ====================================
        # To add menus or menu items, add them to the MENUS dict above

        mb = cast("QMenuBar", self.menuBar())
        for name, entry in self.MENUS.items():
            if callable(entry):
                menu = entry(mmc, self)
                mb.addMenu(menu)
            else:
                menu = cast("QMenu", mb.addMenu(name))
                for action in entry:
                    menu.addAction(self.get_action(action))

        # TOOLBARS =================================
        # To add toolbars or toolbar items, add them to the TOOLBARS dict above

        for name, tb_entry in self.TOOLBARS.items():
            if callable(tb_entry):
                tb = tb_entry(mmc, self)
                self.addToolBar(tb)
            else:
                tb = cast("QToolBar", self.addToolBar(name))
                for action in tb_entry:
                    tb.addAction(self.get_action(action))

        # populate with default widgets ...
        # eventually this should be configurable and restored from a config file
        for key in (
            WidgetAction.CONFIG_GROUPS,
            WidgetAction.STAGE_CONTROL,
            WidgetAction.MDA_WIDGET,
        ):
            self.get_widget(key)

        # LAYOUT ======================================

        central_wdg = QWidget(self)
        self.setCentralWidget(central_wdg)

        layout = QVBoxLayout(central_wdg)
        layout.addWidget(ImagePreview(mmcore=self._mmc, use_with_mda=False))

    @property
    def mmc(self) -> CMMCorePlus:
        return self._mmc

    def get_action(self, key: ActionKey, create: bool = True) -> QAction:
        """Create a QAction from this key."""
        if key not in self._qactions:
            if not create:
                raise KeyError(
                    f"Action {key} has not been created yet, and 'create' is False"
                )
            # create and cache it
            info: WidgetActionInfo[QWidget] = WidgetActionInfo.for_key(key)
            self._qactions[key] = action = info.to_qaction(self._mmc, self)
            # connect WidgetActions to toggle their widgets
            if isinstance(action.key, WidgetAction):
                action.triggered.connect(self._toggle_action_widget)

        return self._qactions[key]

    def get_widget(self, key: WidgetAction, create: bool = True) -> QWidget:
        """Get (or create) widget for `key`.

        Parameters
        ----------
        key : WidgetAction
            The widget to get.
        create : bool, optional
            Whether to create the widget if it doesn't exist yet, by default True.

        Raises
        ------
        KeyError
            If the widget doesn't exist and `create` is False.
        """
        if key not in self._qwidgets:
            if not create:
                raise KeyError(
                    f"Widget {key} has not been created yet, and 'create' is False"
                )
            self._inner_widgets[key] = widget = key.create_widget(self)

            # override closeEvent to uncheck the corresponding QAction
            # FIXME: this still doesn't work for some QDialogs
            def _closeEvent(a0: QCloseEvent | None = None) -> None:
                if action := self._qactions.get(key):
                    action.setChecked(False)
                if isinstance(a0, QCloseEvent):
                    superCloseEvent(a0)

            superCloseEvent = widget.closeEvent
            widget.closeEvent = _closeEvent  # type: ignore [method-assign]

            # also hook up QDialog's finished signal to closeEvent
            if isinstance(widget, QDialog):
                widget.finished.connect(_closeEvent)

            if dock_area := key.dock_area():
                self._dock_widgets[key] = dw = QDockWidget(key.value, self)
                dw.setWidget(widget)
                dw.closeEvent = _closeEvent  # type: ignore [assignment]
                self.addDockWidget(dock_area, dw)

            # toggle checked state of QAction if it exists
            # can this go somewhere else?
            if action := self._qactions.get(key):
                action.setChecked(True)

        return self._qwidgets[key]

    def _toggle_action_widget(self, checked: bool) -> None:
        """Callback that toggles the visibility of a widget.

        This is connected to the triggered signal of WidgetAction QActions above in
        `get_action`, so it is assumed that the sender is a QCoreAction with a
        WidgetAction key.  Calling otherwise will do nothing.
        """
        if not (
            isinstance(action := self.sender(), QCoreAction)
            and isinstance((key := action.key), WidgetAction)
        ):
            return

        widget = self.get_widget(key)
        widget.setVisible(checked)
        if checked:
            widget.raise_()


# ---------------------------------- ndv Viewers manager ----------------------------


# NOTE: we make this a QObject mostly so that the lifetime of this object is tied to
# the lifetime of the parent QMainWindow.  If inheriting from QObject is removed in
# the future, make sure not to store a strong reference to this main_window
class _ViewersManager(QObject):
    """Object that mediates a connection between the MDA experiment and ndv viewers.

    Parameters
    ----------
    parent : QWidget
        The parent widget.
    mmcore : CMMCorePlus
        The CMMCorePlus instance.
    """

    def __init__(self, parent: QWidget, mmcore: CMMCorePlus):
        super().__init__(parent)
        self._mmc = mmcore

        # weakref map of {sequence_uid: ndv.ArrayViewer}
        self._seq_viewers = WeakValueDictionary[str, ndv.ArrayViewer]()
        # currently active viewer
        self._active_viewer: ndv.ArrayViewer | None = None

        # We differentiate between handlers that were created by someone else, and
        # gathered using mda.get_output_handlers(), vs handlers that were created by us.
        # because we need to call frameReady/sequenceFinished manually on the latter.
        self._handler: SupportsFrameReady | None = None
        self._own_handler: TensorStoreHandler | None = None

        # CONNECTIONS ---------------------------------------------------------

        self._mmc.mda.events.sequenceStarted.connect(self._on_sequence_started)
        self._mmc.mda.events.frameReady.connect(self._on_frame_ready)
        self._mmc.mda.events.sequenceFinished.connect(self._on_sequence_finished)

    def _on_sequence_started(
        self, sequence: useq.MDASequence, meta: SummaryMetaV1
    ) -> None:
        """Called when a new MDA sequence has been started.

        We grab the first handler in the list of output handlers, or create a new
        TensorStoreHandler if none exist. Then we create a new ndv viewer and show it.
        """
        self._own_handler = self._handler = None
        if handlers := self._mmc.mda.get_output_handlers():
            # someone else has created a handler for this sequence
            self._handler = handlers[0]
        else:
            # if it does not exist, create a new TensorStoreHandler
            self._own_handler = TensorStoreHandler(driver="zarr", kvstore="memory://")
            self._own_handler.reset(sequence)

        # since the handler is empty at this point, create a ndv viewer with no data
        self._active_viewer = viewer = self._create_ndv_viewer(sequence)
        self._seq_viewers[str(sequence.uid)] = viewer

    def _on_frame_ready(
        self, frame: np.ndarray, event: useq.MDAEvent, meta: FrameMetaV1
    ) -> None:
        """Create a viewer if it does not exist, otherwise update the current index."""
        # at this point the viewer should exist
        if self._own_handler is not None:
            self._own_handler.frameReady(frame, event, meta)

        if (viewer := self._active_viewer) is None:
            return

        # if the viewer does not yet have data, it's likely the very first frame
        # so update the viewer's data source to the underlying handlers store
        if viewer.data_wrapper is None:
            handler = self._handler or self._own_handler
            if isinstance(handler, TensorStoreHandler):
                # TODO: temporary. maybe create the DataWrapper for the handlers
                viewer.data = handler.store
            else:
                warnings.warn(
                    f"don't know how to show data of type {type(handler)}",
                    stacklevel=2,
                )
        # otherwise update the sliders to the most recently acquired frame
        else:
            # Add a small delay to make sure the data are available in the handler
            # This is a bit of a hack to get around the data handlers can write data
            # asynchronously, so the data may not be available immediately to the viewer
            # after the handler's frameReady method is called.
            current_index = viewer.display_model.current_index
            QTimer.singleShot(5, lambda: current_index.update(event.index.items()))

    def _on_sequence_finished(self, sequence: useq.MDASequence) -> None:
        """Called when a sequence has finished."""
        if self._own_handler is not None:
            self._own_handler.sequenceFinished(sequence)
        # cleanup pointers somehow?

    def _create_ndv_viewer(self, sequence: MDASequence) -> ndv.ArrayViewer:
        """Create a new ndv viewer with no data."""
        ndv_viewer = ndv.ArrayViewer()
        q_viewer = cast("QWidget", ndv_viewer.widget())

        if isinstance(par := self.parent(), QWidget):
            q_viewer.setParent(par)

        sha = str(sequence.uid)[:8]
        q_viewer.setObjectName(f"ndv-{sha}")
        q_viewer.setWindowTitle(f"MDA {sha}")
        q_viewer.setWindowFlags(Qt.WindowType.Dialog)
        q_viewer.show()
        return ndv_viewer
