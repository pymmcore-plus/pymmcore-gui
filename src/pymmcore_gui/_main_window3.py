from __future__ import annotations

from enum import Enum
from typing import ClassVar

from pymmcore_plus import CMMCorePlus
from superqt import QIconifyIcon

from pymmcore_gui._qt.Qlementine import NavigationBar
from pymmcore_gui._qt.QtCore import QPoint, Qt, Signal
from pymmcore_gui._qt.QtGui import QAction, QActionGroup, QIcon
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

DEFAULT_SIDEBAR_WIDTH = 180
DEFAULT_PANEL_HEIGHT = 120
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

    panel_toggled = Signal(str)  # panel_id or "" to collapse

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
    def active_panel(self) -> str | None:
        return self._active

    @property
    def collapsible(self) -> bool:
        return self._collapsible

    @collapsible.setter
    def collapsible(self, value: bool) -> None:
        self._collapsible = value

    @property
    def panel_ids(self) -> list[str]:
        return list(self._buttons)

    def add_panel(
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

    def set_active(self, panel_id: str | None) -> None:
        """Programmatically activate (or deactivate) a panel."""
        if panel_id:
            self._toggle(panel_id)
        elif self._active:
            self._toggle(self._active)

    def deselect(self) -> None:
        """Uncheck the active button without emitting panel_toggled."""
        if self._active and self._active in self._buttons:
            self._buttons[self._active].setChecked(False)
        self._active = None

    def activate_first(self) -> None:
        """Activate the first panel if any exist."""
        first = next(iter(self._buttons), None)
        if first:
            self._activate_without_collapse(first)

    def _activate_without_collapse(self, panel_id: str) -> None:
        """Set panel as active (checked) without allowing collapse toggle."""
        if self._active and self._active in self._buttons:
            self._buttons[self._active].setChecked(False)
        self._active = panel_id
        self._buttons[panel_id].setChecked(True)
        self.panel_toggled.emit(panel_id)

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
            self.panel_toggled.emit("")
        else:
            if self._active and self._active in self._buttons:
                self._buttons[self._active].setChecked(False)
            self._active = panel_id
            self._buttons[panel_id].setChecked(True)
            self.panel_toggled.emit(panel_id)


# ---- Sidebar Container ---------------------------------------------------


class SidebarContainer(QWidget):
    """ActivityBar + QStackedWidget pair.

    The activity bar can be positioned relative to the sidebar:
    - side: activity bar is external (placed in outer layout by parent)
    - top/bottom: activity bar is bundled with the stack in a combined widget
    - hidden: activity bar is not shown
    """

    panel_toggled = Signal(str)  # forwarded from activity_bar
    ab_position_changed = Signal(ActivityBarPosition)

    def __init__(
        self,
        *,
        default_ab_position: str = "side",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.activity_bar = ActivityBar(self)
        self.stack = QStackedWidget()
        self.stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._panels: dict[str, QWidget] = {}
        self._default_ab_position = default_ab_position
        self._ab_position = ActivityBarPosition.DEFAULT

        self.stack.setMinimumWidth(MIN_SIDEBAR_WIDTH)

        # Combined container for top/bottom activity bar positions
        self._combined = QWidget()
        self._combined.setMinimumWidth(MIN_SIDEBAR_WIDTH)
        self._combined_layout = QVBoxLayout(self._combined)
        self._combined_layout.setContentsMargins(0, 0, 0, 0)
        self._combined_layout.setSpacing(0)

        # Forward activity bar signal
        self.activity_bar.panel_toggled.connect(self.panel_toggled)

        # Enable context menu on activity bar and stack
        self.activity_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.activity_bar.customContextMenuRequested.connect(self._show_context_menu)
        self.stack.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.stack.customContextMenuRequested.connect(self._show_context_menu_stack)

    # ---- public API -------------------------------------------------------

    @property
    def resolved_ab_position(self) -> str:
        """Return effective position: 'side', 'top', 'bottom', or 'hidden'."""
        if self._ab_position == ActivityBarPosition.DEFAULT:
            return self._default_ab_position
        return self._ab_position.value

    @property
    def is_ab_external(self) -> bool:
        return self.resolved_ab_position == "side"

    @property
    def splitter_widget(self) -> QWidget:
        """The widget to place into a splitter."""
        if self.resolved_ab_position in ("top", "bottom"):
            return self._combined
        return self.stack

    @property
    def is_collapsed(self) -> bool:
        w = self.splitter_widget
        return not w.isVisible() or _splitter_size(w) == 0

    def set_ab_position(self, pos: ActivityBarPosition) -> None:
        self._ab_position = pos

    def arrange(self) -> None:
        """Rearrange activity bar and stack for current position."""
        pos = self.resolved_ab_position

        # Detach both from wherever they currently live.
        # setParent(None) also removes from any layout they were in.
        self.activity_bar.setParent(None)
        self.stack.setParent(None)

        # Only allow collapsing the sidebar when the activity bar
        # is on the side (external). When top/bottom/hidden, the
        # activity bar lives with the sidebar so collapsing would
        # hide the toggle buttons too.
        self.activity_bar.collapsible = pos == "side"

        if pos == "top":
            self._combined_layout.addWidget(self.activity_bar)
            self._combined_layout.addWidget(self.stack, 1)
            self.activity_bar.show()
        elif pos == "bottom":
            self._combined_layout.addWidget(self.stack, 1)
            self._combined_layout.addWidget(self.activity_bar)
            self.activity_bar.show()
        elif pos == "side":
            self.activity_bar.show()
        else:  # hidden
            self.activity_bar.hide()

    def add_panel(
        self,
        panel_id: str,
        title: str,
        widget: QWidget,
        *,
        icon: QIcon | None = None,
    ) -> None:
        self.activity_bar.add_panel(panel_id, title, icon=icon)
        self.stack.addWidget(widget)
        self._panels[panel_id] = widget

    def activate(self, panel_id: str) -> None:
        """Show a specific panel by id."""
        if panel_id not in self._panels:
            return
        self.stack.setCurrentWidget(self._panels[panel_id])
        widget = self.splitter_widget
        widget.show()
        _ensure_splitter_size(widget, DEFAULT_SIDEBAR_WIDTH)

    def toggle(self) -> None:
        """Toggle sidebar visibility. Show first/active panel, or collapse."""
        if self.is_collapsed:
            active = self.activity_bar.active_panel
            if active:
                self.activate(active)
            else:
                self.activity_bar.activate_first()
        else:
            self.collapse()

    def deselect(self) -> None:
        """Deselect the active AB button without hiding the widget.

        Used when the splitter snaps to zero - the widget stays in the
        splitter (so drag-to-restore works) but the button state updates.
        """
        self.activity_bar.deselect()

    def restore_from_drag(self) -> None:
        """Re-activate the first panel after being dragged from zero.

        Updates button state and stack only — does NOT emit panel_toggled,
        so the splitter sizes (which the user is actively dragging) are not
        disturbed.
        """
        first = next(iter(self._panels), None)
        if first:
            ab = self.activity_bar
            if ab._active and ab._active in ab._buttons:
                ab._buttons[ab._active].setChecked(False)
            ab._active = first
            ab._buttons[first].setChecked(True)
            self.stack.setCurrentWidget(self._panels[first])

    def collapse(self) -> None:
        """Fully hide the sidebar."""
        self.splitter_widget.hide()
        self.deselect()

    # ---- context menu -----------------------------------------------------

    def _show_context_menu(self, pos: QPoint) -> None:
        self._build_context_menu().exec(self.activity_bar.mapToGlobal(pos))

    def _show_context_menu_stack(self, pos: QPoint) -> None:
        self._build_context_menu().exec(self.stack.mapToGlobal(pos))

    def _build_context_menu(self) -> QMenu:
        menu = QMenu(self.activity_bar)

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
            self.ab_position_changed.emit(pos)


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


# ---- Mode Widgets ---------------------------------------------------------


def _make_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("font-size: 18px; color: gray;")
    return lbl


class ConfigureModeWidget(QWidget):
    """Placeholder for the Configure mode."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(_make_label("Configure Mode"))


class AcquireModeWidget(QWidget):
    """VS Code-style workbench layout for the Acquire mode."""

    visibility_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._panel_alignment = PanelAlignment.CENTER
        self._root_splitter: QSplitter | None = None

        # Saved sidebar/panel sizes in pixels (survive alignment rebuilds)
        self._left_px = DEFAULT_SIDEBAR_WIDTH
        self._right_px = DEFAULT_SIDEBAR_WIDTH
        self._panel_px = DEFAULT_PANEL_HEIGHT

        # ---- leaf widgets (never destroyed) ----
        self._left_sidebar = SidebarContainer(default_ab_position="side")
        self._right_sidebar = SidebarContainer(default_ab_position="top")
        self._editor_tabs = QTabWidget()
        self._editor_tabs.setTabsClosable(True)
        self._editor_tabs.setMovable(True)
        self._bottom_panel = BottomPanel()

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
            sb.panel_toggled.connect(self._on_sidebar_toggled)
            sb.ab_position_changed.connect(self._on_ab_position_changed)

        # ---- placeholder content ----
        self._left_sidebar.add_panel(
            "explorer",
            "Explorer",
            _make_label("Primary Side Bar\n(Explorer)"),
        )
        self._left_sidebar.activity_bar.set_active("explorer")

        self._right_sidebar.add_panel(
            "properties",
            "Properties",
            _make_label("Secondary Side Bar\n(Properties)"),
        )
        self._right_sidebar.activity_bar.set_active("properties")

        self._editor_tabs.addTab(_make_label("Editor Area"), "Tab 1")
        self._bottom_panel.addTab(_make_label("Panel\n(Terminal / Output)"), "Terminal")

        # ---- build initial splitter tree ----
        self._rebuild_layout()

    # ---- public API -------------------------------------------------------

    @property
    def left_sidebar(self) -> SidebarContainer:
        return self._left_sidebar

    @property
    def right_sidebar(self) -> SidebarContainer:
        return self._right_sidebar

    @property
    def bottom_panel(self) -> BottomPanel:
        return self._bottom_panel

    @property
    def editor_tabs(self) -> QTabWidget:
        return self._editor_tabs

    @property
    def panel_alignment(self) -> PanelAlignment:
        return self._panel_alignment

    @property
    def is_panel_visible(self) -> bool:
        return (
            self._bottom_panel.isVisible() and _splitter_size(self._bottom_panel) != 0
        )

    def set_panel_alignment(self, alignment: PanelAlignment) -> None:
        if alignment == self._panel_alignment:
            return
        self._panel_alignment = alignment
        self._rebuild_layout()

    def toggle_sidebar(self, sidebar: SidebarContainer) -> None:
        """Toggle a sidebar, transferring space to/from the editor only."""
        if sidebar.is_collapsed:
            active = sidebar.activity_bar.active_panel
            if active:
                self._restore_sidebar(sidebar, active)
            else:
                # activate_first fires panel_toggled → _on_sidebar_toggled
                sidebar.activity_bar.activate_first()
        else:
            self._collapse_sidebar(sidebar)
        self.visibility_changed.emit()

    def toggle_panel(self) -> None:
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
        self.visibility_changed.emit()

    # ---- layout rebuild ---------------------------------------------------

    def _detach_leaf_widgets(self) -> None:
        """Detach all reusable widgets from the splitter tree."""
        for sb in (self._left_sidebar, self._right_sidebar):
            # Detach both possible splitter widgets unconditionally.
            # splitter_widget returns _combined or stack depending on the
            # *current* ab_position, but the *previous* layout may have used
            # the other one. Leaving the old widget parented to the root
            # splitter would cause it to be destroyed with the splitter.
            sb._combined.setParent(None)
            sb.stack.setParent(None)
            sb.activity_bar.setParent(None)
        self._editor_tabs.setParent(None)
        self._bottom_panel.setParent(None)

    def _rebuild_layout(self) -> None:
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
            if self._left_sidebar.is_ab_external:
                self._outer_layout.addWidget(self._left_sidebar.activity_bar)
            self._outer_layout.addWidget(self._splitter_container, 1)
            if self._right_sidebar.is_ab_external:
                self._outer_layout.addWidget(self._right_sidebar.activity_bar)

            # Build splitter tree
            root = self._build_splitter_tree()
            self._root_splitter = root
            self._splitter_layout.addWidget(root)

            # Mark sidebar/panel widgets as collapsible and connect signals
            collapsible_widgets = {
                self._left_sidebar.splitter_widget,
                self._right_sidebar.splitter_widget,
                self._bottom_panel,
            }
            self._configure_splitters(root, collapsible_widgets)

            self._restore_sizes()
        finally:
            self.setUpdatesEnabled(True)

    def _build_splitter_tree(self) -> QSplitter:
        V = Qt.Orientation.Vertical
        H = Qt.Orientation.Horizontal
        left = self._left_sidebar.splitter_widget
        right = self._right_sidebar.splitter_widget
        editor = self._editor_tabs
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
        for sb in (self._left_sidebar, self._right_sidebar):
            w = sb.splitter_widget
            if not w.isVisible():
                continue
            size = _splitter_size(w)
            if size == 0 and sb.activity_bar.active_panel is not None:
                sb.deselect()
            elif size > 0 and sb.activity_bar.active_panel is None:
                sb.restore_from_drag()
        self.visibility_changed.emit()

    # ---- size persistence across rebuilds ---------------------------------

    def _save_sizes(self) -> None:
        """Save sidebar/panel sizes as absolute pixel values."""
        left = self._left_sidebar.splitter_widget
        right = self._right_sidebar.splitter_widget
        panel = self._bottom_panel

        if left.isVisible() and left.width() > 0:
            self._left_px = left.width()
        if right.isVisible() and right.width() > 0:
            self._right_px = right.width()
        if panel.isVisible() and panel.height() > 0:
            self._panel_px = panel.height()

    @staticmethod
    def _splitter_avail(splitter: QSplitter, fallback: int) -> int:
        """Available widget space in a splitter (excludes handle pixels)."""
        total = sum(splitter.sizes())
        if total > 0:
            return total
        # Not yet laid out — estimate from fallback minus handles
        handles = (splitter.count() - 1) * splitter.handleWidth()
        return max(fallback - handles, 1)

    def _restore_sizes(self) -> None:
        """Restore splitter sizes using saved pixel values.

        The editor gets the residual from actual available widget space
        (sum of sizes), so no handle-width drift accumulates.
        """
        root = self._root_splitter
        if root is None:
            return

        cont_w = self._splitter_container.width() or 1200
        cont_h = self._splitter_container.height() or 800
        lw = self._left_px
        rw = self._right_px
        ph = self._panel_px
        align = self._panel_alignment

        if align == PanelAlignment.CENTER:
            # root = H[left, V[editor, panel], right]
            v = root.widget(1)
            avail = self._splitter_avail(root, cont_w)
            root.setSizes([lw, avail - lw - rw, rw])
            avail_v = self._splitter_avail(v, cont_h)
            v.setSizes([avail_v - ph, ph])

        elif align == PanelAlignment.JUSTIFY:
            # root = V[H[left, editor, right], panel]
            h = root.widget(0)
            avail_v = self._splitter_avail(root, cont_h)
            root.setSizes([avail_v - ph, ph])
            avail_h = self._splitter_avail(h, cont_w)
            h.setSizes([lw, avail_h - lw - rw, rw])

        elif align == PanelAlignment.LEFT:
            # root = H[V[H[left, editor], panel], right]
            v = root.widget(0)
            inner_h = v.widget(0)
            avail = self._splitter_avail(root, cont_w)
            root.setSizes([avail - rw, rw])
            avail_v = self._splitter_avail(v, cont_h)
            v.setSizes([avail_v - ph, ph])
            avail_ih = self._splitter_avail(inner_h, avail - rw)
            inner_h.setSizes([lw, avail_ih - lw])

        elif align == PanelAlignment.RIGHT:
            # root = H[left, V[H[editor, right], panel]]
            v = root.widget(1)
            inner_h = v.widget(0)
            avail = self._splitter_avail(root, cont_w)
            root.setSizes([lw, avail - lw])
            avail_v = self._splitter_avail(v, cont_h)
            v.setSizes([avail_v - ph, ph])
            avail_ih = self._splitter_avail(inner_h, avail - lw)
            inner_h.setSizes([avail_ih - rw, rw])

    # ---- sidebar toggling -------------------------------------------------

    def _collapse_sidebar(self, sidebar: SidebarContainer) -> None:
        """Collapse a sidebar, giving all freed space to the editor."""
        widget = sidebar.splitter_widget
        parent = widget.parentWidget()
        if not isinstance(parent, QSplitter):
            sidebar.collapse()
            return
        # Save current fraction before collapsing
        self._save_sizes()
        idx = parent.indexOf(widget)
        sizes = parent.sizes()
        freed = sizes[idx]
        sizes[idx] = 0
        # Give all freed space to the editor's slice in this splitter
        editor_idx = self._editor_index_in(parent)
        if editor_idx >= 0:
            sizes[editor_idx] += freed
        parent.setSizes(sizes)
        sidebar.deselect()

    def _restore_sidebar(self, sidebar: SidebarContainer, panel_id: str) -> None:
        """Restore a sidebar, taking space only from the editor."""
        # Show the widget and update button state directly — avoid
        # sidebar.activate() which calls _ensure_splitter_size, and avoid
        # _activate_without_collapse which emits panel_toggled (re-entering).
        if panel_id in sidebar._panels:
            sidebar.stack.setCurrentWidget(sidebar._panels[panel_id])
        widget = sidebar.splitter_widget
        widget.show()
        ab = sidebar.activity_bar
        if ab._active and ab._active in ab._buttons:
            ab._buttons[ab._active].setChecked(False)
        ab._active = panel_id
        ab._buttons[panel_id].setChecked(True)

        parent = widget.parentWidget()
        if not isinstance(parent, QSplitter):
            return
        is_left = sidebar is self._left_sidebar
        sb_px = max(self._left_px if is_left else self._right_px, DEFAULT_SIDEBAR_WIDTH)
        idx = parent.indexOf(widget)
        sizes = parent.sizes()
        # Take space only from the editor
        editor_idx = self._editor_index_in(parent)
        if editor_idx >= 0:
            sizes[editor_idx] = max(sizes[editor_idx] - sb_px, 1)
        sizes[idx] = sb_px
        parent.setSizes(sizes)

    def _editor_index_in(self, splitter: QSplitter) -> int:
        """Find the index of the editor (or sub-splitter containing it)."""
        for i in range(splitter.count()):
            w = splitter.widget(i)
            if w is self._editor_tabs or (
                isinstance(w, QSplitter) and w.isAncestorOf(self._editor_tabs)
            ):
                return i
        return -1

    def _on_sidebar_toggled(self, panel_id: str) -> None:
        sidebar: SidebarContainer = self.sender()  # type: ignore[assignment]
        if panel_id:
            self._restore_sidebar(sidebar, panel_id)
        else:
            self._collapse_sidebar(sidebar)
        self.visibility_changed.emit()

    def _on_ab_position_changed(self) -> None:
        self._rebuild_layout()


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
        self._acquire_mode = AcquireModeWidget()

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

        # ---- layout toggle buttons ----
        self._left_sb_btn = self._make_toggle_btn(
            "Toggle Primary Side Bar",
            "codicon:layout-sidebar-left",
            self._toggle_left_sidebar,
        )
        self._panel_btn = self._make_toggle_btn(
            "Toggle Panel",
            "codicon:layout-panel",
            self._toggle_panel,
        )
        self._right_sb_btn = self._make_toggle_btn(
            "Toggle Secondary Side Bar",
            "codicon:layout-sidebar-right",
            self._toggle_right_sidebar,
        )

        # ---- panel alignment cycle button ----
        self._panel_align_btn = QToolButton()
        self._panel_align_btn.setAutoRaise(True)
        self._panel_align_btn.setToolTip("Panel Alignment")
        self._panel_align_btn.clicked.connect(self._cycle_panel_alignment)
        self._update_panel_align_icon()

        # Sync toggle buttons when any part visibility changes
        self._acquire_mode.visibility_changed.connect(self._update_layout_icons)

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
    def acquire_mode(self) -> AcquireModeWidget:
        return self._acquire_mode

    @property
    def configure_mode(self) -> ConfigureModeWidget:
        return self._configure_mode

    # ---- internals --------------------------------------------------------

    @staticmethod
    def _make_toggle_btn(tooltip: str, icon_key: str, slot: object) -> QToolButton:
        btn = QToolButton()
        btn.setAutoRaise(True)
        btn.setToolTip(tooltip)
        btn.setIcon(QIconifyIcon(icon_key))
        btn.clicked.connect(slot)
        return btn

    def _on_mode_changed(self) -> None:
        self._mode_stack.setCurrentIndex(self._navigation.currentIndex())

    # ---- layout toggle buttons --------------------------------------------

    def _update_layout_icons(self) -> None:
        acq = self._acquire_mode
        left_on = not acq.left_sidebar.is_collapsed
        panel_on = acq.is_panel_visible
        right_on = not acq.right_sidebar.is_collapsed

        self._left_sb_btn.setIcon(
            QIconifyIcon(
                "codicon:layout-sidebar-left"
                if left_on
                else "codicon:layout-sidebar-left-off"
            )
        )
        self._panel_btn.setIcon(
            QIconifyIcon(
                "codicon:layout-panel" if panel_on else "codicon:layout-panel-off"
            )
        )
        self._right_sb_btn.setIcon(
            QIconifyIcon(
                "codicon:layout-sidebar-right"
                if right_on
                else "codicon:layout-sidebar-right-off"
            )
        )

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
        current = self._acquire_mode.panel_alignment
        idx = cycle.index(current) if current in cycle else -1
        next_align = cycle[(idx + 1) % len(cycle)]
        self._acquire_mode.set_panel_alignment(next_align)
        self._update_panel_align_icon()

    def _update_panel_align_icon(self) -> None:
        align = self._acquire_mode.panel_alignment
        icon_key = self._PANEL_ALIGN_ICONS.get(align, "codicon:layout-panel-center")
        self._panel_align_btn.setIcon(QIconifyIcon(icon_key))
        self._panel_align_btn.setToolTip(f"Panel Alignment: {align.value.capitalize()}")

    def _toggle_left_sidebar(self) -> None:
        self._acquire_mode.toggle_sidebar(self._acquire_mode.left_sidebar)
        self._update_layout_icons()

    def _toggle_panel(self) -> None:
        self._acquire_mode.toggle_panel()
        self._update_layout_icons()

    def _toggle_right_sidebar(self) -> None:
        self._acquire_mode.toggle_sidebar(self._acquire_mode.right_sidebar)
        self._update_layout_icons()
