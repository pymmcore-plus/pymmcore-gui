from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from superqt import QIconifyIcon

from pymmcore_gui._layout import (
    ActivityBar,
    ActivityBarPosition,
    PaneContainer,
    PanelAlignment,
    ViewContainerLocation,
    WorkbenchWidget,
    splitter_size,
)
from pymmcore_gui._main_window3 import MicroManagerGUI, _make_label
from pymmcore_gui._qt.QtCore import Qt
from pymmcore_gui._qt.QtWidgets import QApplication, QSplitter

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytestqt.qtbot import QtBot

    from pymmcore_gui._qt.QtWidgets import QLabel

L = ViewContainerLocation


# ---- Fixtures -------------------------------------------------------------


@pytest.fixture()
def activity_bar(qtbot: QtBot) -> ActivityBar:
    ab = ActivityBar()
    qtbot.addWidget(ab)
    return ab


@pytest.fixture()
def h_activity_bar(qtbot: QtBot) -> ActivityBar:
    ab = ActivityBar(Qt.Orientation.Horizontal)
    qtbot.addWidget(ab)
    return ab


@pytest.fixture()
def container(qtbot: QtBot) -> PaneContainer:
    c = PaneContainer()
    qtbot.addWidget(c)
    c.addPanel("alpha", "Alpha", _label())
    c.addPanel("beta", "Beta", _label())
    return c


@pytest.fixture()
def workbench(qtbot: QtBot) -> WorkbenchWidget:
    w = _make_workbench()
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    return w


@pytest.fixture()
def gui(qtbot: QtBot) -> Iterator[MicroManagerGUI]:
    g = MicroManagerGUI()
    qtbot.addWidget(g)
    yield g


def _label() -> QLabel:
    return _make_label("test")


def _make_workbench() -> WorkbenchWidget:
    """Create a WorkbenchWidget with minimal content for testing."""
    w = WorkbenchWidget()
    w.addView("explorer", "Explorer", _label(), L.LEFT_SIDEBAR)
    w.leftSidebar.activityBar.setActive("explorer")
    w.addView("properties", "Properties", _label(), L.RIGHT_SIDEBAR)
    w.rightSidebar.activityBar.setActive("properties")
    w.addView("terminal", "Terminal", _label(), L.PANEL)
    w.bottomPanel.activityBar.setActive("terminal")
    return w


# ---- ActivityBar tests ----------------------------------------------------


class TestActivityBar:
    def test_add_panel(self, activity_bar: ActivityBar) -> None:
        btn = activity_bar.addPanel("foo", "Foo")
        assert "foo" in activity_bar.panelIds
        assert btn.toolTip() == "Foo"
        assert btn.text() == "Fo"  # fallback: first 2 chars

    def test_default_orientation_is_vertical(self, activity_bar: ActivityBar) -> None:
        assert activity_bar.orientation == Qt.Orientation.Vertical

    def test_horizontal_orientation(self, h_activity_bar: ActivityBar) -> None:
        assert h_activity_bar.orientation == Qt.Orientation.Horizontal
        h_activity_bar.addPanel("a", "A")
        h_activity_bar.addPanel("b", "B")
        assert len(h_activity_bar.panelIds) == 2

    def test_set_active_emits_signal(
        self, activity_bar: ActivityBar, qtbot: QtBot
    ) -> None:
        activity_bar.addPanel("a", "A")
        activity_bar.addPanel("b", "B")

        with qtbot.waitSignal(activity_bar.panelToggled) as blocker:
            activity_bar.setActive("a")
        assert blocker.args == ["a"]
        assert activity_bar.activePanel == "a"

    def test_toggle_deactivates_when_collapsible(
        self, activity_bar: ActivityBar, qtbot: QtBot
    ) -> None:
        activity_bar.addPanel("x", "X")
        activity_bar.setActive("x")
        assert activity_bar.activePanel == "x"

        with qtbot.waitSignal(activity_bar.panelToggled) as blocker:
            activity_bar.setActive("x")  # toggle off
        assert blocker.args == [""]
        assert activity_bar.activePanel is None

    def test_toggle_blocked_when_not_collapsible(
        self, activity_bar: ActivityBar
    ) -> None:
        activity_bar.addPanel("x", "X")
        activity_bar.collapsible = False
        activity_bar.setActive("x")

        activity_bar.setActive("x")  # should NOT toggle off
        assert activity_bar.activePanel == "x"

    def test_deselect(self, activity_bar: ActivityBar) -> None:
        activity_bar.addPanel("a", "A")
        activity_bar.setActive("a")
        assert activity_bar.activePanel == "a"

        activity_bar.deselect()
        assert activity_bar.activePanel is None

    def test_activate_first(self, activity_bar: ActivityBar, qtbot: QtBot) -> None:
        activity_bar.addPanel("first", "First")
        activity_bar.addPanel("second", "Second")

        with qtbot.waitSignal(activity_bar.panelToggled) as blocker:
            activity_bar.activateFirst()
        assert blocker.args == ["first"]
        assert activity_bar.activePanel == "first"

    def test_switching_panels(self, activity_bar: ActivityBar, qtbot: QtBot) -> None:
        activity_bar.addPanel("a", "A")
        activity_bar.addPanel("b", "B")
        activity_bar.setActive("a")

        with qtbot.waitSignal(activity_bar.panelToggled) as blocker:
            activity_bar.setActive("b")
        assert blocker.args == ["b"]
        assert activity_bar.activePanel == "b"


# ---- PaneContainer tests -------------------------------------------------


class TestPaneContainer:
    def test_add_panel_adds_to_stack(self, container: PaneContainer) -> None:
        assert container.stack.count() == 2
        assert "alpha" in container.activityBar.panelIds
        assert "beta" in container.activityBar.panelIds

    def test_panel_toggled_forwarded(
        self, container: PaneContainer, qtbot: QtBot
    ) -> None:
        with qtbot.waitSignal(container.panelToggled) as blocker:
            container.activityBar.setActive("alpha")
        assert blocker.args == ["alpha"]

    def test_toggle_collapse_and_restore(self, container: PaneContainer) -> None:
        container.activityBar.setActive("alpha")
        assert container.activityBar.activePanel == "alpha"

        container.collapse()
        assert container.activityBar.activePanel is None

    def test_toggle_method(self, container: PaneContainer) -> None:
        container.activityBar.setActive("alpha")
        container.splitterWidget.show()
        container.toggle()  # should collapse
        assert container.activityBar.activePanel is None

    def test_ab_position_default(self, container: PaneContainer) -> None:
        assert container.resolvedAbPosition == "side"
        assert container.isAbExternal is True

    def test_ab_position_top(self, container: PaneContainer) -> None:
        container.setAbPosition(ActivityBarPosition.TOP)
        assert container.resolvedAbPosition == "top"
        assert container.isAbExternal is False
        assert container.splitterWidget is container._combined

    def test_ab_position_hidden(self, container: PaneContainer) -> None:
        container.setAbPosition(ActivityBarPosition.HIDDEN)
        container.arrange()
        assert not container.activityBar.isVisible()

    def test_ab_position_changed_signal(
        self, container: PaneContainer, qtbot: QtBot
    ) -> None:
        container.setAbPosition(ActivityBarPosition.BOTTOM)
        container._ab_position = ActivityBarPosition.DEFAULT  # reset
        with qtbot.waitSignal(container.abPositionChanged) as blocker:
            container.abPositionChanged.emit(ActivityBarPosition.BOTTOM)
        assert blocker.args == [ActivityBarPosition.BOTTOM]

    def test_restore_from_drag(self, container: PaneContainer) -> None:
        container.deselect()
        assert container.activityBar.activePanel is None

        container.restoreFromDrag()
        assert container.activityBar.activePanel == "alpha"

    def test_arrange_side(self, container: PaneContainer) -> None:
        container.setAbPosition(ActivityBarPosition.DEFAULT)
        container.arrange()
        assert container.activityBar.collapsible is True
        assert container.activityBar.isVisible()

    def test_arrange_top(self, container: PaneContainer) -> None:
        container.setAbPosition(ActivityBarPosition.TOP)
        container.arrange()
        assert container.activityBar.collapsible is False
        assert container.activityBar.parent() is container._combined

    def test_horizontal_activity_bar(self, qtbot: QtBot) -> None:
        c = PaneContainer(orientation=Qt.Orientation.Horizontal)
        qtbot.addWidget(c)
        c.addPanel("a", "A", _label())
        c.addPanel("b", "B", _label())
        assert c.activityBar.orientation == Qt.Orientation.Horizontal
        assert len(c.activityBar.panelIds) == 2


# ---- WorkbenchWidget tests ------------------------------------------------


class TestWorkbenchWidget:
    def test_initial_state(self, workbench: WorkbenchWidget) -> None:
        assert workbench.panelAlignment == PanelAlignment.CENTER
        assert workbench.leftSidebar.activityBar.activePanel == "explorer"
        assert workbench.rightSidebar.activityBar.activePanel == "properties"
        assert workbench.bottomPanel.activityBar.activePanel == "terminal"
        assert workbench._root_splitter is not None

    @pytest.mark.parametrize("alignment", list(PanelAlignment))
    def test_set_panel_alignment_rebuilds(
        self, workbench: WorkbenchWidget, alignment: PanelAlignment
    ) -> None:
        workbench.setPanelAlignment(alignment)
        assert workbench.panelAlignment == alignment
        assert workbench._root_splitter is not None

    def test_set_same_alignment_is_noop(self, workbench: WorkbenchWidget) -> None:
        old_splitter = workbench._root_splitter
        workbench.setPanelAlignment(PanelAlignment.CENTER)
        assert workbench._root_splitter is old_splitter

    def test_sidebar_toggle_emits_visibility_changed(
        self, workbench: WorkbenchWidget, qtbot: QtBot
    ) -> None:
        with qtbot.waitSignal(workbench.visibilityChanged):
            workbench.leftSidebar.activityBar.setActive("explorer")

    def test_toggle_panel(self, workbench: WorkbenchWidget, qtbot: QtBot) -> None:
        assert workbench.isPanelVisible
        with qtbot.waitSignal(workbench.visibilityChanged):
            workbench.togglePanel()
        assert not workbench.isPanelVisible

        with qtbot.waitSignal(workbench.visibilityChanged):
            workbench.togglePanel()
        assert workbench.isPanelVisible

    def test_sidebar_collapse_and_restore(self, workbench: WorkbenchWidget) -> None:
        left = workbench.leftSidebar
        left.collapse()
        assert left.activityBar.activePanel is None

        left.toggle()
        assert left.activityBar.activePanel is not None

    def test_alignment_switch_preserves_leaf_widgets(
        self, workbench: WorkbenchWidget
    ) -> None:
        """Leaf widgets must survive splitter tree rebuilds."""
        editor = workbench.centralWidget
        left_stack = workbench.leftSidebar.stack
        right_stack = workbench.rightSidebar.stack
        panel_stack = workbench.bottomPanel.stack

        for alignment in PanelAlignment:
            workbench.setPanelAlignment(alignment)
            assert editor.parent() is not None
            assert left_stack.parent() is not None
            assert right_stack.parent() is not None
            assert panel_stack.parent() is not None

    def test_toggle_actions_exist(self, workbench: WorkbenchWidget) -> None:
        assert workbench.toggleLeftSidebarAction is not None
        assert workbench.togglePanelAction is not None
        assert workbench.toggleRightSidebarAction is not None

    def test_action_icons_update(self, workbench: WorkbenchWidget) -> None:
        """setActionIcons + toggle cycle should not crash."""
        workbench.setActionIcons(
            workbench.toggleLeftSidebarAction,
            QIconifyIcon("codicon:layout-sidebar-left"),
            QIconifyIcon("codicon:layout-sidebar-left-off"),
        )
        workbench.toggleLeftSidebar()
        workbench.toggleLeftSidebar()

    def test_add_view_routes_to_correct_container(self, qtbot: QtBot) -> None:
        w = WorkbenchWidget()
        qtbot.addWidget(w)
        w.addView("a", "A", _label(), L.LEFT_SIDEBAR)
        w.addView("b", "B", _label(), L.RIGHT_SIDEBAR)
        w.addView("c", "C", _label(), L.PANEL)
        assert "a" in w.leftSidebar.activityBar.panelIds
        assert "b" in w.rightSidebar.activityBar.panelIds
        assert "c" in w.bottomPanel.activityBar.panelIds

    def test_bottom_panel_is_pane_container(self, workbench: WorkbenchWidget) -> None:
        """Bottom panel should be a PaneContainer, not a QTabWidget."""
        assert isinstance(workbench.bottomPanel, PaneContainer)
        assert (
            workbench.bottomPanel.activityBar.orientation == Qt.Orientation.Horizontal
        )

    def test_state_buttons(self, workbench: WorkbenchWidget) -> None:
        """stateButtons() returns a widget with 4 auto-raise buttons."""
        from pymmcore_gui._qt.QtWidgets import QToolButton

        w = workbench.stateButtons()
        buttons = w.findChildren(QToolButton)
        assert len(buttons) == 4
        assert all(b.autoRaise() for b in buttons)

    def test_state_buttons_creates_independent_instances(
        self, workbench: WorkbenchWidget
    ) -> None:
        w1 = workbench.stateButtons()
        w2 = workbench.stateButtons()
        assert w1 is not w2

    def test_cycle_panel_alignment(self, workbench: WorkbenchWidget) -> None:
        expected = [
            PanelAlignment.RIGHT,
            PanelAlignment.JUSTIFY,
            PanelAlignment.LEFT,
            PanelAlignment.CENTER,
        ]
        for align in expected:
            workbench.cyclePanelAlignment()
            assert workbench.panelAlignment == align


# ---- MicroManagerGUI tests ------------------------------------------------


class TestMicroManagerGUI:
    def test_construction(self, gui: MicroManagerGUI) -> None:
        assert gui.windowTitle() == "pyMM"
        assert gui.acquire_mode is not None
        assert gui.configure_mode is not None

    def test_mode_switching(self, gui: MicroManagerGUI) -> None:
        gui._navigation.setCurrentIndex(0)
        assert gui._mode_stack.currentWidget() is gui.configure_mode

        gui._navigation.setCurrentIndex(1)
        assert gui._mode_stack.currentWidget() is gui.acquire_mode

    def test_toggle_left_sidebar(self, gui: MicroManagerGUI) -> None:
        gui.show()
        wb = gui.acquire_mode
        assert not wb.leftSidebar.isCollapsed

        wb.toggleLeftSidebar()
        assert wb.leftSidebar.activityBar.activePanel is None

        wb.toggleLeftSidebar()
        assert wb.leftSidebar.activityBar.activePanel is not None

    def test_toggle_right_sidebar(self, gui: MicroManagerGUI) -> None:
        gui.show()
        wb = gui.acquire_mode
        assert not wb.rightSidebar.isCollapsed

        wb.toggleRightSidebar()
        assert wb.rightSidebar.activityBar.activePanel is None

        wb.toggleRightSidebar()
        assert wb.rightSidebar.activityBar.activePanel is not None

    def test_toggle_panel(self, gui: MicroManagerGUI) -> None:
        gui.show()
        wb = gui.acquire_mode
        assert wb.isPanelVisible

        wb.togglePanel()
        assert not wb.isPanelVisible

        wb.togglePanel()
        assert wb.isPanelVisible

    def test_cycle_panel_alignment(self, gui: MicroManagerGUI) -> None:
        gui.show()
        wb = gui.acquire_mode
        expected_cycle = [
            PanelAlignment.RIGHT,
            PanelAlignment.JUSTIFY,
            PanelAlignment.LEFT,
            PanelAlignment.CENTER,
        ]
        for expected in expected_cycle:
            wb.cyclePanelAlignment()
            assert wb.panelAlignment == expected


# ---- Splitter size stability tests ----------------------------------------

TOLERANCE = 4  # pixels — accounts for integer rounding and handle widths


@pytest.fixture()
def shown_workbench(qtbot: QtBot) -> WorkbenchWidget:
    """WorkbenchWidget shown and laid out so splitter sizes are meaningful."""
    w = _make_workbench()
    qtbot.addWidget(w)
    w.resize(1200, 800)
    w.show()
    qtbot.waitExposed(w)

    QApplication.processEvents()
    w._save_sizes()
    return w


def _sidebar_sizes(wb: WorkbenchWidget) -> tuple[int, int, int]:
    """Return (left_width, editor_width, right_width) from actual geometry."""
    left = wb.leftSidebar.splitterWidget
    right = wb.rightSidebar.splitterWidget
    editor = wb.centralWidget
    return left.width(), editor.width(), right.width()


def test_alignment_cycle_no_drift(shown_workbench: WorkbenchWidget) -> None:
    """Cycling through all alignments and back should preserve sizes."""
    wb = shown_workbench
    left0, _, right0 = _sidebar_sizes(wb)

    alignments = list(PanelAlignment)
    for _ in range(3):
        for alignment in alignments:
            wb.setPanelAlignment(alignment)
            QApplication.processEvents()

    wb.setPanelAlignment(PanelAlignment.CENTER)
    QApplication.processEvents()
    left_after, _, right_after = _sidebar_sizes(wb)

    assert abs(left_after - left0) <= TOLERANCE, (
        f"left sidebar drifted: {left0} -> {left_after}"
    )
    assert abs(right_after - right0) <= TOLERANCE, (
        f"right sidebar drifted: {right0} -> {right_after}"
    )


def test_sidebar_toggle_preserves_other_sidebar(
    shown_workbench: WorkbenchWidget,
) -> None:
    """Toggling one sidebar should not change the other sidebar's size."""
    wb = shown_workbench
    _, _, right0 = _sidebar_sizes(wb)

    for _ in range(5):
        wb.toggleLeftSidebar()
        wb.toggleLeftSidebar()

    _, _, right_after = _sidebar_sizes(wb)
    assert abs(right_after - right0) <= TOLERANCE, (
        f"right sidebar changed when toggling left: {right0} -> {right_after}"
    )


def test_sidebar_toggle_restores_own_size(
    shown_workbench: WorkbenchWidget,
) -> None:
    """A sidebar should return to its original size after toggle cycle."""
    wb = shown_workbench
    left0, _, _ = _sidebar_sizes(wb)

    wb.toggleLeftSidebar()  # collapse
    wb.toggleLeftSidebar()  # restore

    left_after, _, _ = _sidebar_sizes(wb)
    assert abs(left_after - left0) <= TOLERANCE, (
        f"left sidebar size changed after toggle cycle: {left0} -> {left_after}"
    )


def test_panel_toggle_preserves_sidebar_sizes(
    shown_workbench: WorkbenchWidget,
) -> None:
    """Toggling the bottom panel should not affect sidebar widths."""
    wb = shown_workbench
    left0, _, right0 = _sidebar_sizes(wb)

    for _ in range(5):
        wb.togglePanel()
        wb.togglePanel()

    left_after, _, right_after = _sidebar_sizes(wb)
    assert abs(left_after - left0) <= TOLERANCE, (
        f"left sidebar changed when toggling panel: {left0} -> {left_after}"
    )
    assert abs(right_after - right0) <= TOLERANCE, (
        f"right sidebar changed when toggling panel: {right0} -> {right_after}"
    )


def test_alignment_change_preserves_collapsed_state(
    shown_workbench: WorkbenchWidget,
) -> None:
    """Changing panel alignment should not resurrect a collapsed sidebar."""
    wb = shown_workbench

    wb.toggleRightSidebar()
    QApplication.processEvents()
    assert wb.rightSidebar.isCollapsed

    wb.setPanelAlignment(PanelAlignment.RIGHT)
    QApplication.processEvents()

    right_w = wb.rightSidebar.splitterWidget
    assert splitter_size(right_w) == 0, (
        "collapsed right sidebar reappeared after alignment change"
    )

    wb.setPanelAlignment(PanelAlignment.CENTER)
    QApplication.processEvents()
    wb.toggleLeftSidebar()
    QApplication.processEvents()
    assert wb.leftSidebar.isCollapsed

    wb.setPanelAlignment(PanelAlignment.JUSTIFY)
    QApplication.processEvents()

    left_w = wb.leftSidebar.splitterWidget
    assert splitter_size(left_w) == 0, (
        "collapsed left sidebar reappeared after alignment change"
    )


def test_rapid_alignment_cycling_with_collapses(
    shown_workbench: WorkbenchWidget,
) -> None:
    """Rapid alignment changes with collapsed parts must not corrupt state."""
    wb = shown_workbench

    wb.toggleRightSidebar()
    wb.togglePanel()
    QApplication.processEvents()

    for _ in range(3):
        for align in PanelAlignment:
            wb.setPanelAlignment(align)

    QApplication.processEvents()

    assert wb.rightSidebar.isCollapsed
    assert not wb.isPanelVisible
    assert not wb.leftSidebar.isCollapsed
    assert wb.leftSidebar.activityBar.activePanel is not None


def test_collapse_all_then_change_alignment(
    shown_workbench: WorkbenchWidget,
) -> None:
    """Collapsing everything then changing alignment must not crash."""
    wb = shown_workbench

    wb.toggleLeftSidebar()
    wb.toggleRightSidebar()
    wb.togglePanel()
    QApplication.processEvents()

    for align in PanelAlignment:
        wb.setPanelAlignment(align)
        QApplication.processEvents()
        assert wb.leftSidebar.isCollapsed
        assert wb.rightSidebar.isCollapsed
        assert not wb.isPanelVisible


def test_drag_restore_does_not_disturb_other_sidebar(
    shown_workbench: WorkbenchWidget,
) -> None:
    """Drag-to-zero then drag-back should not shift other sidebar."""
    wb = shown_workbench
    left0, _, _ = _sidebar_sizes(wb)
    right_widget = wb.rightSidebar.splitterWidget
    parent = right_widget.parentWidget()
    assert parent is not None

    assert isinstance(parent, QSplitter)
    idx = parent.indexOf(right_widget)

    # Simulate drag to zero
    sizes = parent.sizes()
    freed = sizes[idx]
    editor_idx = wb._editor_index_in(parent)
    sizes[editor_idx] += freed
    sizes[idx] = 0
    parent.setSizes(sizes)
    wb._on_splitter_moved()

    assert wb.rightSidebar.activityBar.activePanel is None

    # Simulate drag back
    sizes = parent.sizes()
    restore_px = 150
    sizes[editor_idx] -= restore_px
    sizes[idx] = restore_px
    parent.setSizes(sizes)
    wb._on_splitter_moved()

    left_after, _, _ = _sidebar_sizes(wb)
    assert abs(left_after - left0) <= TOLERANCE, (
        f"left sidebar shifted during right drag-restore: {left0} -> {left_after}"
    )
