from __future__ import annotations

from pymmcore_gui._qt.QtCore import Qt, Signal
from pymmcore_gui._qt.QtGui import QAction, QIcon, QPalette
from pymmcore_gui._qt.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ._enums import PanelAlignment, ViewContainerLocation
from ._pane_container import PaneContainer
from ._splitter_utils import (
    DEFAULT_PANEL_HEIGHT,
    DEFAULT_SIDEBAR_WIDTH,
    MIN_PANEL_HEIGHT,
    splitter_size,
)


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

        # Saved sizes in pixels (survive alignment rebuilds)
        self._left_px = DEFAULT_SIDEBAR_WIDTH
        self._right_px = DEFAULT_SIDEBAR_WIDTH
        self._panel_px = DEFAULT_PANEL_HEIGHT
        self._left_collapsed = False
        self._right_collapsed = False
        self._panel_collapsed = False

        # ---- leaf widgets (never destroyed) ----
        self._containers: dict[ViewContainerLocation, PaneContainer] = {
            ViewContainerLocation.LEFT_SIDEBAR: PaneContainer(
                default_ab_position="side",
            ),
            ViewContainerLocation.RIGHT_SIDEBAR: PaneContainer(
                default_ab_position="top",
            ),
            ViewContainerLocation.PANEL: PaneContainer(
                orientation=Qt.Orientation.Horizontal,
                default_ab_position="top",
            ),
        }
        self._central = central or QWidget()
        self._central.setAutoFillBackground(True)
        self._central.setBackgroundRole(QPalette.ColorRole.Base)
        self._central.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Convenience aliases
        self._left_sidebar = self._containers[ViewContainerLocation.LEFT_SIDEBAR]
        self._right_sidebar = self._containers[ViewContainerLocation.RIGHT_SIDEBAR]
        self._bottom_panel = self._containers[ViewContainerLocation.PANEL]
        self._bottom_panel.splitterWidget.setMinimumHeight(MIN_PANEL_HEIGHT)

        # ---- toggle actions ----
        self._toggle_left_action = QAction("Toggle Primary Side Bar", self)
        self._toggle_left_action.triggered.connect(self.toggleLeftSidebar)

        self._toggle_panel_action = QAction("Toggle Panel", self)
        self._toggle_panel_action.triggered.connect(self.togglePanel)

        self._toggle_right_action = QAction("Toggle Secondary Side Bar", self)
        self._toggle_right_action.triggered.connect(self.toggleRightSidebar)

        self._cycle_align_action = QAction("Cycle Panel Alignment", self)
        self._cycle_align_action.triggered.connect(self.cyclePanelAlignment)

        self.visibilityChanged.connect(self._update_action_icons)

        # ---- layout ----
        self._outer_layout = QHBoxLayout(self)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setSpacing(0)

        self._splitter_container = QWidget()
        self._splitter_layout = QVBoxLayout(self._splitter_container)
        self._splitter_layout.setContentsMargins(0, 0, 0, 0)
        self._splitter_layout.setSpacing(0)

        # ---- wire container signals ----
        for container in self._containers.values():
            container.panelToggled.connect(self._on_container_toggled)
            container.abPositionChanged.connect(self._on_ab_position_changed)

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
    def leftSidebar(self) -> PaneContainer:
        return self._left_sidebar

    @property
    def rightSidebar(self) -> PaneContainer:
        return self._right_sidebar

    @property
    def bottomPanel(self) -> PaneContainer:
        return self._bottom_panel

    @property
    def centralWidget(self) -> QWidget:
        return self._central

    @property
    def panelAlignment(self) -> PanelAlignment:
        return self._panel_alignment

    @property
    def isPanelVisible(self) -> bool:
        return not self._bottom_panel.isCollapsed

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

    @property
    def cyclePanelAlignmentAction(self) -> QAction:
        return self._cycle_align_action

    def setActionIcons(
        self,
        action: QAction,
        icon_on: QIcon,
        icon_off: QIcon,
    ) -> None:
        """Set the on/off icon pair for a toggle action."""
        action.setProperty("iconOn", icon_on)
        action.setProperty("iconOff", icon_off)
        action.setIcon(icon_on)

    def setAlignmentIcons(self, icons: dict[PanelAlignment, QIcon]) -> None:
        """Set per-alignment icons for the cycle action."""
        self._cycle_align_action.setProperty("alignIcons", icons)
        current = icons.get(self._panel_alignment)
        if current:
            self._cycle_align_action.setIcon(current)

    def stateButtons(self, parent: QWidget | None = None) -> QWidget:
        """Create and return a widget with layout-control buttons.

        Each call creates a new set of buttons bound to the workbench's
        actions. The caller places the returned widget wherever it wants.
        """
        return WorkbenchStateButtons(self)

    # ---- public methods ---------------------------------------------------

    _PANEL_ALIGN_CYCLE = (
        PanelAlignment.LEFT,
        PanelAlignment.CENTER,
        PanelAlignment.RIGHT,
        PanelAlignment.JUSTIFY,
    )

    def setPanelAlignment(self, alignment: PanelAlignment) -> None:
        if alignment == self._panel_alignment:
            return
        self._panel_alignment = alignment
        self._rebuild_layout()
        self._update_align_icon()

    def cyclePanelAlignment(self) -> None:
        """Advance to the next panel alignment in the cycle."""
        cycle = self._PANEL_ALIGN_CYCLE
        current = self._panel_alignment
        idx = cycle.index(current) if current in cycle else -1
        self.setPanelAlignment(cycle[(idx + 1) % len(cycle)])

    def addView(
        self,
        view_id: str,
        title: str,
        widget: QWidget,
        location: ViewContainerLocation = ViewContainerLocation.LEFT_SIDEBAR,
        *,
        icon: QIcon | None = None,
    ) -> None:
        """Add a view to a container by location."""
        self._containers[location].addPanel(view_id, title, widget, icon=icon)

    def toggleLeftSidebar(self) -> None:
        self._toggle_container(self._left_sidebar)
        self.visibilityChanged.emit()

    def toggleRightSidebar(self) -> None:
        self._toggle_container(self._right_sidebar)
        self.visibilityChanged.emit()

    def togglePanel(self) -> None:
        self._toggle_container(self._bottom_panel)
        self.visibilityChanged.emit()

    # ---- layout rebuild ---------------------------------------------------

    def _detach_leaf_widgets(self) -> None:
        """Detach all reusable widgets from the splitter tree."""
        for container in self._containers.values():
            container._combined.setParent(None)
            container.stack.setParent(None)
            container.activityBar.setParent(None)
        self._central.setParent(None)

    def _rebuild_layout(self) -> None:
        self._rebuilding = True
        self.setUpdatesEnabled(False)
        try:
            if self._root_splitter is not None:
                self._save_sizes()
                self._detach_leaf_widgets()
                self._root_splitter.setParent(None)
                self._root_splitter.deleteLater()

            while self._outer_layout.count():
                self._outer_layout.takeAt(0)

            for container in self._containers.values():
                container.arrange()

            if self._left_sidebar.isAbExternal:
                self._outer_layout.addWidget(self._left_sidebar.activityBar)
            self._outer_layout.addWidget(self._splitter_container, 1)
            if self._right_sidebar.isAbExternal:
                self._outer_layout.addWidget(self._right_sidebar.activityBar)

            root = self._build_splitter_tree()
            self._root_splitter = root
            self._splitter_layout.addWidget(root)

            collapsible_widgets = {c.splitterWidget for c in self._containers.values()}
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
        panel = self._bottom_panel.splitterWidget
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
        for container, flag_attr in (
            (self._left_sidebar, "_left_collapsed"),
            (self._right_sidebar, "_right_collapsed"),
            (self._bottom_panel, "_panel_collapsed"),
        ):
            w = container.splitterWidget
            if not w.isVisible():
                continue
            size = splitter_size(w)
            if size == 0 and container.activityBar.activePanel is not None:
                container.deselect()
                setattr(self, flag_attr, True)
            elif size > 0 and container.activityBar.activePanel is None:
                container.restoreFromDrag()
                setattr(self, flag_attr, False)
        self.visibilityChanged.emit()

    # ---- size persistence across rebuilds ---------------------------------

    def _save_sizes(self) -> None:
        """Save container pixel sizes (not collapsed state)."""
        for container, attr in (
            (self._left_sidebar, "_left_px"),
            (self._right_sidebar, "_right_px"),
            (self._bottom_panel, "_panel_px"),
        ):
            sz = splitter_size(container.splitterWidget)
            if sz > 0:
                setattr(self, attr, sz)

    @staticmethod
    def _splitter_avail(splitter: QSplitter, fallback: int) -> int:
        """Available widget space in a splitter."""
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

    # ---- container toggling -----------------------------------------------

    def _toggle_container(self, container: PaneContainer) -> None:
        """Toggle a container, transferring space to/from the editor."""
        if container.isCollapsed:
            active = container.activityBar.activePanel
            if active:
                self._restore_container(container, active)
            else:
                container.activityBar.activateFirst()
        else:
            self._collapse_container(container)

    def _collapse_container(self, container: PaneContainer) -> None:
        """Collapse a container, giving all freed space to the editor."""
        widget = container.splitterWidget
        parent = widget.parentWidget()
        if not isinstance(parent, QSplitter):
            container.collapse()
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
        container.deselect()
        if container is self._left_sidebar:
            self._left_collapsed = True
        elif container is self._right_sidebar:
            self._right_collapsed = True
        else:
            self._panel_collapsed = True

    def _restore_container(self, container: PaneContainer, panel_id: str) -> None:
        """Restore a container, taking space only from the editor."""
        if panel_id in container._panels:
            container.stack.setCurrentWidget(container._panels[panel_id])
        widget = container.splitterWidget
        widget.show()
        container.activityBar.setActiveSilent(panel_id)

        parent = widget.parentWidget()
        if not isinstance(parent, QSplitter):
            return
        if container is self._left_sidebar:
            target_px = max(self._left_px, DEFAULT_SIDEBAR_WIDTH)
        elif container is self._right_sidebar:
            target_px = max(self._right_px, DEFAULT_SIDEBAR_WIDTH)
        else:
            target_px = max(self._panel_px, DEFAULT_PANEL_HEIGHT)
        idx = parent.indexOf(widget)
        sizes = parent.sizes()
        editor_idx = self._editor_index_in(parent)
        if editor_idx >= 0:
            sizes[editor_idx] = max(sizes[editor_idx] - target_px, 1)
        sizes[idx] = target_px
        parent.setSizes(sizes)
        if container is self._left_sidebar:
            self._left_collapsed = False
        elif container is self._right_sidebar:
            self._right_collapsed = False
        else:
            self._panel_collapsed = False

    def _editor_index_in(self, splitter: QSplitter) -> int:
        """Find the index of the editor (or sub-splitter containing it)."""
        for i in range(splitter.count()):
            w = splitter.widget(i)
            if w is self._central or (
                isinstance(w, QSplitter) and w.isAncestorOf(self._central)
            ):
                return i
        return -1

    def _on_container_toggled(self, panel_id: str) -> None:
        container: PaneContainer = self.sender()  # type: ignore[assignment,unused-ignore]
        if panel_id:
            self._restore_container(container, panel_id)
        else:
            self._collapse_container(container)
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

    def _update_align_icon(self) -> None:
        icons = self._cycle_align_action.property("alignIcons")
        if isinstance(icons, dict):
            icon = icons.get(self._panel_alignment)
            if icon is not None:
                self._cycle_align_action.setIcon(icon)
        self._cycle_align_action.setToolTip(
            f"Panel Alignment: {self._panel_alignment.value.capitalize()}"
        )


class WorkbenchStateButtons(QWidget):
    def __init__(self, workbench: WorkbenchWidget) -> None:
        super().__init__(workbench)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for action in (
            workbench._cycle_align_action,
            workbench._toggle_left_action,
            workbench._toggle_panel_action,
            workbench._toggle_right_action,
        ):
            btn = QToolButton(workbench)
            btn.setDefaultAction(action)
            btn.setAutoRaise(True)
            layout.addWidget(btn)
