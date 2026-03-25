from __future__ import annotations

from enum import Enum
from typing import ClassVar

from pymmcore_plus import CMMCorePlus
from superqt import QIconifyIcon

from pymmcore_gui._qt.Qlementine import NavigationBar
from pymmcore_gui._qt.QtCore import QPoint, Qt, Signal
from pymmcore_gui._qt.QtGui import QAction, QActionGroup, QIcon, QPalette
from pymmcore_gui._qt.QtOpenGLWidgets import QOpenGLWidget
from pymmcore_gui._qt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ._main_window import ICON

DEFAULT_SIDEBAR_WIDTH = 300
DEFAULT_PANEL_HEIGHT = 220
MIN_SIDEBAR_WIDTH = 160
MIN_PANEL_HEIGHT = 100


def _splitter_size(widget: QWidget) -> int:
    """Return the size allocated to *widget* by its parent QSplitter."""
    parent = widget.parent()
    if not isinstance(parent, QSplitter):
        return -1
    idx = parent.indexOf(widget)
    if idx < 0:
        return -1
    return parent.sizes()[idx]


def _ensure_splitter_size(widget: QWidget, size: int) -> None:
    """If widget is collapsed in a QSplitter, restore it to *size*."""
    parent = widget.parent()
    if not isinstance(parent, QSplitter):
        return
    idx = parent.indexOf(widget)
    if idx < 0:
        return
    sizes = parent.sizes()
    if sizes[idx] == 0:
        sizes[idx] = size
        parent.setSizes(sizes)


class PanelAlignment(Enum):
    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"
    JUSTIFY = "justify"


class ActivityBarPosition(Enum):
    DEFAULT = "default"
    TOP = "top"
    BOTTOM = "bottom"
    HIDDEN = "hidden"


# ---- Activity Bar --------------------------------------------------------


class ActivityBar(QWidget):
    """Vertical icon strip that toggles sidebar panels."""

    panelToggled = Signal(str)  # panel_id or "" to collapse

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._buttons: dict[str, QToolButton] = {}
        self._active: str | None = None
        self._collapsible = True

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(2)
        self._layout.addStretch()

    # ---- public API -------------------------------------------------------

    @property
    def activePanel(self) -> str | None:
        return self._active

    @property
    def collapsible(self) -> bool:
        return self._collapsible

    @collapsible.setter
    def collapsible(self, value: bool) -> None:
        self._collapsible = value

    @property
    def panelIds(self) -> list[str]:
        return list(self._buttons)

    def addPanel(
        self, panel_id: str, text: str, *, icon: QIcon | None = None
    ) -> QToolButton:
        btn = QToolButton()
        btn.setToolTip(text)
        if icon:
            btn.setIcon(icon)
        else:
            btn.setText(text[:2])
        btn.setCheckable(True)
        btn.setAutoExclusive(False)
        btn.setObjectName(panel_id)
        btn.clicked.connect(self._on_clicked)

        self._buttons[panel_id] = btn
        self._layout.insertWidget(self._layout.count() - 1, btn)
        return btn

    def setActive(self, panel_id: str | None) -> None:
        """Programmatically activate (or deactivate) a panel."""
        if panel_id:
            self._toggle(panel_id)
        elif self._active:
            self._toggle(self._active)

    def deselect(self) -> None:
        """Uncheck the active button without emitting panelToggled."""
        if self._active and self._active in self._buttons:
            self._buttons[self._active].setChecked(False)
        self._active = None

    def activateFirst(self) -> None:
        """Activate the first panel if any exist."""
        first = next(iter(self._buttons), None)
        if first:
            self._activate_without_collapse(first)

    def setActiveSilent(self, panel_id: str) -> None:
        """Update checked state without emitting panelToggled."""
        if self._active and self._active in self._buttons:
            self._buttons[self._active].setChecked(False)
        self._active = panel_id
        self._buttons[panel_id].setChecked(True)

    def _activate_without_collapse(self, panel_id: str) -> None:
        """Set panel as active (checked) without allowing collapse toggle."""
        self.setActiveSilent(panel_id)
        self.panelToggled.emit(panel_id)

    # ---- internals --------------------------------------------------------

    def _on_clicked(self) -> None:
        panel_id = self.sender().objectName()
        self._toggle(panel_id)

    def _toggle(self, panel_id: str) -> None:
        if self._active == panel_id:
            if not self._collapsible:
                self._buttons[panel_id].setChecked(True)
                return
            self._buttons[panel_id].setChecked(False)
            self._active = None
            self.panelToggled.emit("")
        else:
            if self._active and self._active in self._buttons:
                self._buttons[self._active].setChecked(False)
            self._active = panel_id
            self._buttons[panel_id].setChecked(True)
            self.panelToggled.emit(panel_id)


# ---- Sidebar Container ---------------------------------------------------


class SidebarContainer(QWidget):
    """ActivityBar + QStackedWidget pair.

    The activity bar can be positioned relative to the sidebar:
    - side: activity bar is external (placed in outer layout by parent)
    - top/bottom: activity bar is bundled with the stack in a combined widget
    - hidden: activity bar is not shown
    """

    panelToggled = Signal(str)  # forwarded from activityBar
    abPositionChanged = Signal(ActivityBarPosition)

    def __init__(
        self,
        *,
        default_ab_position: str = "side",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._activity_bar = ActivityBar(self)
        self._stack = QStackedWidget()
        self._stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._panels: dict[str, QWidget] = {}
        self._default_ab_position = default_ab_position
        self._ab_position = ActivityBarPosition.DEFAULT

        self._stack.setMinimumWidth(MIN_SIDEBAR_WIDTH)

        # Combined container for top/bottom activity bar positions
        self._combined = QWidget()
        self._combined.setMinimumWidth(MIN_SIDEBAR_WIDTH)
        self._combined_layout = QVBoxLayout(self._combined)
        self._combined_layout.setContentsMargins(0, 0, 0, 0)
        self._combined_layout.setSpacing(0)

        # Forward activity bar signal
        self._activity_bar.panelToggled.connect(self.panelToggled)

        # Enable context menu on activity bar and stack
        self._activity_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._activity_bar.customContextMenuRequested.connect(self._show_context_menu)
        self._stack.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._stack.customContextMenuRequested.connect(self._show_context_menu_stack)

    # ---- public API -------------------------------------------------------

    @property
    def activityBar(self) -> ActivityBar:
        return self._activity_bar

    @property
    def stack(self) -> QStackedWidget:
        return self._stack

    @property
    def resolvedAbPosition(self) -> str:
        """Return effective position: 'side', 'top', 'bottom', or 'hidden'."""
        if self._ab_position == ActivityBarPosition.DEFAULT:
            return self._default_ab_position
        return self._ab_position.value

    @property
    def isAbExternal(self) -> bool:
        return self.resolvedAbPosition == "side"

    @property
    def splitterWidget(self) -> QWidget:
        """The widget to place into a splitter."""
        if self.resolvedAbPosition in ("top", "bottom"):
            return self._combined
        return self._stack

    @property
    def isCollapsed(self) -> bool:
        w = self.splitterWidget
        return not w.isVisible() or _splitter_size(w) == 0

    def setAbPosition(self, pos: ActivityBarPosition) -> None:
        self._ab_position = pos

    def arrange(self) -> None:
        """Rearrange activity bar and stack for current position."""
        pos = self.resolvedAbPosition

        # Detach both from wherever they currently live.
        self._activity_bar.setParent(None)
        self._stack.setParent(None)

        # Only allow collapsing the sidebar when the activity bar
        # is on the side (external). When top/bottom/hidden, the
        # activity bar lives with the sidebar so collapsing would
        # hide the toggle buttons too.
        self._activity_bar.collapsible = pos == "side"

        if pos == "top":
            self._combined_layout.addWidget(self._activity_bar)
            self._combined_layout.addWidget(self._stack, 1)
            self._activity_bar.show()
        elif pos == "bottom":
            self._combined_layout.addWidget(self._stack, 1)
            self._combined_layout.addWidget(self._activity_bar)
            self._activity_bar.show()
        elif pos == "side":
            self._activity_bar.show()
        else:  # hidden
            self._activity_bar.hide()

    def addPanel(
        self,
        panel_id: str,
        title: str,
        widget: QWidget,
        *,
        icon: QIcon | None = None,
    ) -> None:
        self._activity_bar.addPanel(panel_id, title, icon=icon)
        self._stack.addWidget(widget)
        self._panels[panel_id] = widget

    def activate(self, panel_id: str) -> None:
        """Show a specific panel by id."""
        if panel_id not in self._panels:
            return
        self._stack.setCurrentWidget(self._panels[panel_id])
        widget = self.splitterWidget
        widget.show()
        _ensure_splitter_size(widget, DEFAULT_SIDEBAR_WIDTH)

    def toggle(self) -> None:
        """Toggle sidebar visibility. Show first/active panel, or collapse."""
        if self.isCollapsed:
            active = self._activity_bar.activePanel
            if active:
                self.activate(active)
            else:
                self._activity_bar.activateFirst()
        else:
            self.collapse()

    def deselect(self) -> None:
        """Deselect the active AB button without hiding the widget.

        Used when the splitter snaps to zero - the widget stays in the
        splitter (so drag-to-restore works) but the button state updates.
        """
        self._activity_bar.deselect()

    def restoreFromDrag(self) -> None:
        """Re-activate the first panel after being dragged from zero.

        Updates button state and stack only — does NOT emit panelToggled,
        so the splitter sizes (which the user is actively dragging) are not
        disturbed.
        """
        first = next(iter(self._panels), None)
        if first:
            self._activity_bar.setActiveSilent(first)
            self._stack.setCurrentWidget(self._panels[first])

    def collapse(self) -> None:
        """Fully hide the sidebar."""
        self.splitterWidget.hide()
        self.deselect()

    # ---- context menu -----------------------------------------------------

    def _show_context_menu(self, pos: QPoint) -> None:
        self._build_context_menu().exec(self._activity_bar.mapToGlobal(pos))

    def _show_context_menu_stack(self, pos: QPoint) -> None:
        self._build_context_menu().exec(self._stack.mapToGlobal(pos))

    def _build_context_menu(self) -> QMenu:
        menu = QMenu(self._activity_bar)

        ab_menu = menu.addMenu("Activity Bar Position")
        group = QActionGroup(ab_menu)
        group.setExclusive(True)

        for pos in ActivityBarPosition:
            action = QAction(pos.value.capitalize(), ab_menu)
            action.setCheckable(True)
            action.setChecked(self._ab_position == pos)
            action.setData(pos)
            action.triggered.connect(self._on_ab_position_action)
            group.addAction(action)
            ab_menu.addAction(action)

        return menu

    def _on_ab_position_action(self) -> None:
        action: QAction = self.sender()  # type: ignore[assignment]
        pos: ActivityBarPosition = action.data()
        if pos != self._ab_position:
            self._ab_position = pos
            self.abPositionChanged.emit(pos)


# ---- Bottom Panel ---------------------------------------------------------


class BottomPanel(QTabWidget):
    """Tabbed panel (terminal / output / problems)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTabPosition(QTabWidget.TabPosition.North)
        self.setMovable(True)
        self.setMinimumHeight(MIN_PANEL_HEIGHT)


# ---- Status Bar -----------------------------------------------------------


class StatusBar(QStatusBar):
    """Status bar with a notification bell."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bell_button = QPushButton(QIconifyIcon("codicon:bell"), "")
        self.bell_button.setFlat(True)
        self.addPermanentWidget(self.bell_button)


# ---- Helper ---------------------------------------------------------------


def _make_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("font-size: 18px; color: gray;")
    return lbl


# ---- Workbench Widget -----------------------------------------------------


class WorkbenchWidget(QWidget):
    """VS Code-style workbench with two sidebars, a central area, and a panel."""

    visibilityChanged = Signal()

    def __init__(
        self,
        central: QWidget | None = None,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._panel_alignment = PanelAlignment.CENTER
        self._root_splitter: QSplitter | None = None
        self._rebuilding = False

        # Saved sidebar/panel sizes in pixels (survive alignment rebuilds)
        self._left_px = DEFAULT_SIDEBAR_WIDTH
        self._right_px = DEFAULT_SIDEBAR_WIDTH
        self._panel_px = DEFAULT_PANEL_HEIGHT
        self._left_collapsed = False
        self._right_collapsed = False
        self._panel_collapsed = False

        # ---- leaf widgets (never destroyed) ----
        self._left_sidebar = SidebarContainer(default_ab_position="side")
        self._right_sidebar = SidebarContainer(default_ab_position="top")
        self._central = central or QWidget()
        self._central.setAutoFillBackground(True)
        self._central.setBackgroundRole(QPalette.ColorRole.Base)
        self._central.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._bottom_panel = BottomPanel()

        # ---- toggle actions ----
        self._toggle_left_action = QAction("Toggle Primary Side Bar", self)
        self._toggle_left_action.triggered.connect(self.toggleLeftSidebar)

        self._toggle_panel_action = QAction("Toggle Panel", self)
        self._toggle_panel_action.triggered.connect(self.togglePanel)

        self._toggle_right_action = QAction("Toggle Secondary Side Bar", self)
        self._toggle_right_action.triggered.connect(self.toggleRightSidebar)

        self.visibilityChanged.connect(self._update_action_icons)

        # ---- layout ----
        self._outer_layout = QHBoxLayout(self)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setSpacing(0)

        self._splitter_container = QWidget()
        self._splitter_layout = QVBoxLayout(self._splitter_container)
        self._splitter_layout.setContentsMargins(0, 0, 0, 0)
        self._splitter_layout.setSpacing(0)

        # ---- wire sidebar signals ----
        for sb in (self._left_sidebar, self._right_sidebar):
            sb.panelToggled.connect(self._on_sidebar_toggled)
            sb.abPositionChanged.connect(self._on_ab_position_changed)

        # ---- build initial splitter tree ----
        self._needs_initial_resize = True
        self._rebuild_layout()

    def showEvent(self, event: object) -> None:
        super().showEvent(event)  # type: ignore[arg-type]
        if self._needs_initial_resize:
            self._needs_initial_resize = False
            self._restore_sizes()

    # ---- public properties ------------------------------------------------

    @property
    def leftSidebar(self) -> SidebarContainer:
        return self._left_sidebar

    @property
    def rightSidebar(self) -> SidebarContainer:
        return self._right_sidebar

    @property
    def bottomPanel(self) -> BottomPanel:
        return self._bottom_panel

    @property
    def centralWidget(self) -> QWidget:
        return self._central

    @property
    def panelAlignment(self) -> PanelAlignment:
        return self._panel_alignment

    @property
    def isPanelVisible(self) -> bool:
        return (
            self._bottom_panel.isVisible() and _splitter_size(self._bottom_panel) != 0
        )

    @property
    def isLeftSidebarVisible(self) -> bool:
        return not self._left_sidebar.isCollapsed

    @property
    def isRightSidebarVisible(self) -> bool:
        return not self._right_sidebar.isCollapsed

    # ---- toggle actions ---------------------------------------------------

    @property
    def toggleLeftSidebarAction(self) -> QAction:
        return self._toggle_left_action

    @property
    def togglePanelAction(self) -> QAction:
        return self._toggle_panel_action

    @property
    def toggleRightSidebarAction(self) -> QAction:
        return self._toggle_right_action

    def setActionIcons(
        self,
        action: QAction,
        icon_on: QIcon,
        icon_off: QIcon,
    ) -> None:
        """Set the on/off icon pair for a toggle action."""
        action.setProperty("iconOn", icon_on)
        action.setProperty("iconOff", icon_off)
        # Set initial icon
        action.setIcon(icon_on)

    # ---- public methods ---------------------------------------------------

    def setPanelAlignment(self, alignment: PanelAlignment) -> None:
        if alignment == self._panel_alignment:
            return
        self._panel_alignment = alignment
        self._rebuild_layout()

    def toggleLeftSidebar(self) -> None:
        self._toggle_sidebar(self._left_sidebar)
        self.visibilityChanged.emit()

    def toggleRightSidebar(self) -> None:
        self._toggle_sidebar(self._right_sidebar)
        self.visibilityChanged.emit()

    def togglePanel(self) -> None:
        """Toggle bottom panel visibility, transferring space to the editor."""
        panel = self._bottom_panel
        parent = panel.parentWidget()
        if not panel.isVisible() or _splitter_size(panel) == 0:
            panel.show()
            if isinstance(parent, QSplitter):
                ph = max(self._panel_px, DEFAULT_PANEL_HEIGHT)
                idx = parent.indexOf(panel)
                sizes = parent.sizes()
                editor_idx = self._editor_index_in(parent)
                if editor_idx >= 0:
                    sizes[editor_idx] = max(sizes[editor_idx] - ph, 1)
                sizes[idx] = ph
                parent.setSizes(sizes)
            else:
                _ensure_splitter_size(panel, DEFAULT_PANEL_HEIGHT)
            self._panel_collapsed = False
        else:
            if isinstance(parent, QSplitter):
                self._save_sizes()
                idx = parent.indexOf(panel)
                sizes = parent.sizes()
                freed = sizes[idx]
                sizes[idx] = 0
                editor_idx = self._editor_index_in(parent)
                if editor_idx >= 0:
                    sizes[editor_idx] += freed
                parent.setSizes(sizes)
            panel.hide()
            self._panel_collapsed = True
        self.visibilityChanged.emit()

    def addLeftPanel(
        self,
        panel_id: str,
        title: str,
        widget: QWidget,
        *,
        icon: QIcon | None = None,
    ) -> None:
        """Add a panel to the left sidebar."""
        self._left_sidebar.addPanel(panel_id, title, widget, icon=icon)

    def addRightPanel(
        self,
        panel_id: str,
        title: str,
        widget: QWidget,
        *,
        icon: QIcon | None = None,
    ) -> None:
        """Add a panel to the right sidebar."""
        self._right_sidebar.addPanel(panel_id, title, widget, icon=icon)

    def addBottomTab(self, widget: QWidget, label: str) -> int:
        """Add a tab to the bottom panel."""
        return self._bottom_panel.addTab(widget, label)

    # ---- layout rebuild ---------------------------------------------------

    def _detach_leaf_widgets(self) -> None:
        """Detach all reusable widgets from the splitter tree."""
        for sb in (self._left_sidebar, self._right_sidebar):
            sb._combined.setParent(None)
            sb.stack.setParent(None)
            sb.activityBar.setParent(None)
        self._central.setParent(None)
        self._bottom_panel.setParent(None)

    def _rebuild_layout(self) -> None:
        self._rebuilding = True
        self.setUpdatesEnabled(False)
        try:
            # Save sizes from current splitters
            if self._root_splitter is not None:
                self._save_sizes()
                self._detach_leaf_widgets()
                self._root_splitter.setParent(None)
                self._root_splitter.deleteLater()

            # Clear outer layout
            while self._outer_layout.count():
                self._outer_layout.takeAt(0)

            # Arrange sidebars (reparents activity bar + stack internally)
            self._left_sidebar.arrange()
            self._right_sidebar.arrange()

            # Rebuild outer: [ext_ab_L?] [splitter_container] [ext_ab_R?]
            if self._left_sidebar.isAbExternal:
                self._outer_layout.addWidget(self._left_sidebar.activityBar)
            self._outer_layout.addWidget(self._splitter_container, 1)
            if self._right_sidebar.isAbExternal:
                self._outer_layout.addWidget(self._right_sidebar.activityBar)

            # Build splitter tree
            root = self._build_splitter_tree()
            self._root_splitter = root
            self._splitter_layout.addWidget(root)

            # Mark sidebar/panel widgets as collapsible and connect signals
            collapsible_widgets = {
                self._left_sidebar.splitterWidget,
                self._right_sidebar.splitterWidget,
                self._bottom_panel,
            }
            self._configure_splitters(root, collapsible_widgets)

            self._restore_sizes()
        finally:
            self._rebuilding = False
            self.setUpdatesEnabled(True)

    def _build_splitter_tree(self) -> QSplitter:
        V = Qt.Orientation.Vertical
        H = Qt.Orientation.Horizontal
        left = self._left_sidebar.splitterWidget
        right = self._right_sidebar.splitterWidget
        editor = self._central
        panel = self._bottom_panel
        align = self._panel_alignment

        if align == PanelAlignment.CENTER:
            v = QSplitter(V)
            v.addWidget(editor)
            v.addWidget(panel)
            root = QSplitter(H)
            root.addWidget(left)
            root.addWidget(v)
            root.addWidget(right)

        elif align == PanelAlignment.JUSTIFY:
            h = QSplitter(H)
            h.addWidget(left)
            h.addWidget(editor)
            h.addWidget(right)
            root = QSplitter(V)
            root.addWidget(h)
            root.addWidget(panel)

        elif align == PanelAlignment.LEFT:
            inner_h = QSplitter(H)
            inner_h.addWidget(left)
            inner_h.addWidget(editor)
            v = QSplitter(V)
            v.addWidget(inner_h)
            v.addWidget(panel)
            root = QSplitter(H)
            root.addWidget(v)
            root.addWidget(right)

        else:  # PanelAlignment.RIGHT
            inner_h = QSplitter(H)
            inner_h.addWidget(editor)
            inner_h.addWidget(right)
            v = QSplitter(V)
            v.addWidget(inner_h)
            v.addWidget(panel)
            root = QSplitter(H)
            root.addWidget(left)
            root.addWidget(v)

        return root

    def _configure_splitters(
        self, splitter: QSplitter, collapsible: set[QWidget]
    ) -> None:
        """Mark collapsible widgets and connect signals, recursively."""
        for i in range(splitter.count()):
            w = splitter.widget(i)
            splitter.setCollapsible(i, w in collapsible)
            if isinstance(w, QSplitter):
                self._configure_splitters(w, collapsible)
        splitter.splitterMoved.connect(self._on_splitter_moved)

    def _on_splitter_moved(self) -> None:
        if self._rebuilding:
            return
        for sb in (self._left_sidebar, self._right_sidebar):
            w = sb.splitterWidget
            if not w.isVisible():
                continue
            is_left = sb is self._left_sidebar
            size = _splitter_size(w)
            if size == 0 and sb.activityBar.activePanel is not None:
                sb.deselect()
                if is_left:
                    self._left_collapsed = True
                else:
                    self._right_collapsed = True
            elif size > 0 and sb.activityBar.activePanel is None:
                sb.restoreFromDrag()
                if is_left:
                    self._left_collapsed = False
                else:
                    self._right_collapsed = False
        self.visibilityChanged.emit()

    # ---- size persistence across rebuilds ---------------------------------

    def _save_sizes(self) -> None:
        """Save sidebar/panel pixel sizes (not collapsed state).

        Collapsed flags are maintained explicitly by toggle/collapse/restore
        methods, not inferred from widget geometry (which can be stale during
        rapid rebuilds).
        """
        left = self._left_sidebar.splitterWidget
        right = self._right_sidebar.splitterWidget
        panel = self._bottom_panel

        sz = _splitter_size(left)
        if sz > 0:
            self._left_px = sz
        sz = _splitter_size(right)
        if sz > 0:
            self._right_px = sz
        sz = _splitter_size(panel)
        if sz > 0:
            self._panel_px = sz

    @staticmethod
    def _splitter_avail(splitter: QSplitter, fallback: int) -> int:
        """Available widget space in a splitter (excludes handle pixels)."""
        total = sum(splitter.sizes())
        if total > 0:
            return total
        handles = (splitter.count() - 1) * splitter.handleWidth()
        return max(fallback - handles, 1)

    def _restore_sizes(self) -> None:
        """Restore splitter sizes using saved pixel values."""
        root = self._root_splitter
        if root is None:
            return

        cont_w = self._splitter_container.width() or 1200
        cont_h = self._splitter_container.height() or 800
        lw = 0 if self._left_collapsed else self._left_px
        rw = 0 if self._right_collapsed else self._right_px
        ph = 0 if self._panel_collapsed else self._panel_px
        align = self._panel_alignment

        if align == PanelAlignment.CENTER:
            v = root.widget(1)
            avail = self._splitter_avail(root, cont_w)
            root.setSizes([lw, avail - lw - rw, rw])
            avail_v = self._splitter_avail(v, cont_h)
            v.setSizes([avail_v - ph, ph])

        elif align == PanelAlignment.JUSTIFY:
            h = root.widget(0)
            avail_v = self._splitter_avail(root, cont_h)
            root.setSizes([avail_v - ph, ph])
            avail_h = self._splitter_avail(h, cont_w)
            h.setSizes([lw, avail_h - lw - rw, rw])

        elif align == PanelAlignment.LEFT:
            v = root.widget(0)
            inner_h = v.widget(0)
            avail = self._splitter_avail(root, cont_w)
            root.setSizes([avail - rw, rw])
            avail_v = self._splitter_avail(v, cont_h)
            v.setSizes([avail_v - ph, ph])
            avail_ih = self._splitter_avail(inner_h, avail - rw)
            inner_h.setSizes([lw, avail_ih - lw])

        elif align == PanelAlignment.RIGHT:
            v = root.widget(1)
            inner_h = v.widget(0)
            avail = self._splitter_avail(root, cont_w)
            root.setSizes([lw, avail - lw])
            avail_v = self._splitter_avail(v, cont_h)
            v.setSizes([avail_v - ph, ph])
            avail_ih = self._splitter_avail(inner_h, avail - lw)
            inner_h.setSizes([avail_ih - rw, rw])

    # ---- sidebar toggling -------------------------------------------------

    def _toggle_sidebar(self, sidebar: SidebarContainer) -> None:
        """Toggle a sidebar, transferring space to/from the editor only."""
        if sidebar.isCollapsed:
            active = sidebar.activityBar.activePanel
            if active:
                self._restore_sidebar(sidebar, active)
            else:
                sidebar.activityBar.activateFirst()
        else:
            self._collapse_sidebar(sidebar)

    def _collapse_sidebar(self, sidebar: SidebarContainer) -> None:
        """Collapse a sidebar, giving all freed space to the editor."""
        widget = sidebar.splitterWidget
        parent = widget.parentWidget()
        if not isinstance(parent, QSplitter):
            sidebar.collapse()
            return
        self._save_sizes()
        idx = parent.indexOf(widget)
        sizes = parent.sizes()
        freed = sizes[idx]
        sizes[idx] = 0
        editor_idx = self._editor_index_in(parent)
        if editor_idx >= 0:
            sizes[editor_idx] += freed
        parent.setSizes(sizes)
        sidebar.deselect()
        if sidebar is self._left_sidebar:
            self._left_collapsed = True
        else:
            self._right_collapsed = True

    def _restore_sidebar(self, sidebar: SidebarContainer, panel_id: str) -> None:
        """Restore a sidebar, taking space only from the editor."""
        if panel_id in sidebar._panels:
            sidebar.stack.setCurrentWidget(sidebar._panels[panel_id])
        widget = sidebar.splitterWidget
        widget.show()
        sidebar.activityBar.setActiveSilent(panel_id)

        parent = widget.parentWidget()
        if not isinstance(parent, QSplitter):
            return
        is_left = sidebar is self._left_sidebar
        sb_px = max(
            self._left_px if is_left else self._right_px,
            DEFAULT_SIDEBAR_WIDTH,
        )
        idx = parent.indexOf(widget)
        sizes = parent.sizes()
        editor_idx = self._editor_index_in(parent)
        if editor_idx >= 0:
            sizes[editor_idx] = max(sizes[editor_idx] - sb_px, 1)
        sizes[idx] = sb_px
        parent.setSizes(sizes)
        if sidebar is self._left_sidebar:
            self._left_collapsed = False
        else:
            self._right_collapsed = False

    def _editor_index_in(self, splitter: QSplitter) -> int:
        """Find the index of the editor (or sub-splitter containing it)."""
        for i in range(splitter.count()):
            w = splitter.widget(i)
            if w is self._central or (
                isinstance(w, QSplitter) and w.isAncestorOf(self._central)
            ):
                return i
        return -1

    def _on_sidebar_toggled(self, panel_id: str) -> None:
        sidebar: SidebarContainer = self.sender()  # type: ignore[assignment]
        if panel_id:
            self._restore_sidebar(sidebar, panel_id)
        else:
            self._collapse_sidebar(sidebar)
        self.visibilityChanged.emit()

    def _on_ab_position_changed(self) -> None:
        self._rebuild_layout()

    def _update_action_icons(self) -> None:
        """Swap on/off icons on each toggle action based on current state."""
        for action, visible in (
            (self._toggle_left_action, self.isLeftSidebarVisible),
            (self._toggle_panel_action, self.isPanelVisible),
            (self._toggle_right_action, self.isRightSidebarVisible),
        ):
            icon = action.property("iconOn" if visible else "iconOff")
            if icon is not None:
                action.setIcon(icon)


# Keep old name as alias for backwards compatibility
AcquireModeWidget = WorkbenchWidget


# ---- Mode Widgets ---------------------------------------------------------


class ConfigureModeWidget(QWidget):
    """Placeholder for the Configure mode."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(_make_label("Configure Mode"))


# ---- Main Window ----------------------------------------------------------


class MicroManagerGUI(QMainWindow):
    def __init__(self, *, mmcore: CMMCorePlus | None = None) -> None:
        super().__init__()
        self.setWindowTitle("pyMM")
        self.setWindowIcon(QIcon(str(ICON)))
        self.setObjectName("MicroManagerGUI")

        self._mmc = mmcore or CMMCorePlus.instance()

        # ---- mode widgets ----
        self._configure_mode = ConfigureModeWidget()
        self._acquire_mode = WorkbenchWidget(central=_make_label("Editor Area"))

        # Populate workbench with placeholder content
        wb = self._acquire_mode
        wb.addLeftPanel(
            "explorer",
            "Explorer",
            _make_label("Primary Side Bar"),
        )
        wb.leftSidebar.activityBar.setActive("explorer")
        wb.addRightPanel(
            "properties",
            "Properties",
            _make_label("Secondary Side Bar"),
        )
        wb.rightSidebar.activityBar.setActive("properties")
        wb.addBottomTab(_make_label("Panel"), "Terminal")

        # ---- mode stack ----
        self._mode_stack = QStackedWidget()
        self._mode_stack.addWidget(self._configure_mode)
        self._mode_stack.addWidget(self._acquire_mode)

        # ---- navigation bar (mode switcher) ----
        self._navigation = NavigationBar()
        self._navigation.setItemsShouldExpand(False)
        self._navigation.addItem("Configure")
        self._navigation.addItem("Acquire")
        self._navigation.setCurrentIndex(1)  # start on Acquire
        self._mode_stack.setCurrentIndex(1)
        self._navigation.currentIndexChanged.connect(self._on_mode_changed)

        # ---- toggle action icons ----
        wb.setActionIcons(
            wb.toggleLeftSidebarAction,
            QIconifyIcon("codicon:layout-sidebar-left"),
            QIconifyIcon("codicon:layout-sidebar-left-off"),
        )
        wb.setActionIcons(
            wb.togglePanelAction,
            QIconifyIcon("codicon:layout-panel"),
            QIconifyIcon("codicon:layout-panel-off"),
        )
        wb.setActionIcons(
            wb.toggleRightSidebarAction,
            QIconifyIcon("codicon:layout-sidebar-right"),
            QIconifyIcon("codicon:layout-sidebar-right-off"),
        )

        # ---- ghost toggle buttons ----
        self._left_sb_btn = self._make_ghost_button(wb.toggleLeftSidebarAction)
        self._panel_btn = self._make_ghost_button(wb.togglePanelAction)
        self._right_sb_btn = self._make_ghost_button(wb.toggleRightSidebarAction)

        # ---- panel alignment cycle button ----
        self._panel_align_btn = QToolButton()
        self._panel_align_btn.setAutoRaise(True)
        self._panel_align_btn.setToolTip("Panel Alignment")
        self._panel_align_btn.clicked.connect(self._cycle_panel_alignment)
        self._update_panel_align_icon()

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(0)
        top_row.addWidget(self._navigation)
        top_row.addStretch()
        top_row.addWidget(self._panel_align_btn)
        top_row.addWidget(self._left_sb_btn)
        top_row.addWidget(self._panel_btn)
        top_row.addWidget(self._right_sb_btn)

        # ---- central layout ----
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(top_row)
        layout.addWidget(self._mode_stack, 1)
        self.setCentralWidget(central)

        # ---- status bar ----
        self._status_bar = StatusBar(self)
        self.setStatusBar(self._status_bar)

        # Pre-init OpenGL surface to avoid flash when adding
        # QOpenGLWidget-based viewers later.
        _gl = QOpenGLWidget(self)
        _gl.setFixedSize(0, 0)
        _gl.close()

        self.resize(1200, 800)

    # ---- public API -------------------------------------------------------

    @property
    def mmcore(self) -> CMMCorePlus:
        return self._mmc

    @property
    def acquire_mode(self) -> WorkbenchWidget:
        return self._acquire_mode

    @property
    def configure_mode(self) -> ConfigureModeWidget:
        return self._configure_mode

    # ---- internals --------------------------------------------------------

    @staticmethod
    def _make_ghost_button(action: QAction) -> QToolButton:
        btn = QToolButton()
        btn.setDefaultAction(action)
        btn.setAutoRaise(True)
        return btn

    def _on_mode_changed(self) -> None:
        self._mode_stack.setCurrentIndex(self._navigation.currentIndex())

    # ---- panel alignment --------------------------------------------------

    _PANEL_ALIGN_CYCLE = (
        PanelAlignment.LEFT,
        PanelAlignment.CENTER,
        PanelAlignment.RIGHT,
        PanelAlignment.JUSTIFY,
    )
    _PANEL_ALIGN_ICONS: ClassVar[dict[PanelAlignment, str]] = {
        PanelAlignment.LEFT: "codicon:layout-panel-left",
        PanelAlignment.CENTER: "codicon:layout-panel-center",
        PanelAlignment.RIGHT: "codicon:layout-panel-right",
        PanelAlignment.JUSTIFY: "codicon:layout-panel-justify",
    }

    def _cycle_panel_alignment(self) -> None:
        cycle = self._PANEL_ALIGN_CYCLE
        current = self._acquire_mode.panelAlignment
        idx = cycle.index(current) if current in cycle else -1
        next_align = cycle[(idx + 1) % len(cycle)]
        self._acquire_mode.setPanelAlignment(next_align)
        self._update_panel_align_icon()

    def _update_panel_align_icon(self) -> None:
        align = self._acquire_mode.panelAlignment
        icon_key = self._PANEL_ALIGN_ICONS.get(align, "codicon:layout-panel-center")
        self._panel_align_btn.setIcon(QIconifyIcon(icon_key))
        self._panel_align_btn.setToolTip(f"Panel Alignment: {align.value.capitalize()}")
