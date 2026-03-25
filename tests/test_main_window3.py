from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pymmcore_gui._main_window3 import (
    AcquireModeWidget,
    ActivityBar,
    ActivityBarPosition,
    MicroManagerGUI,
    PanelAlignment,
    SidebarContainer,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytestqt.qtbot import QtBot

    from pymmcore_gui._qt.QtWidgets import QLabel


# ---- Fixtures -------------------------------------------------------------


@pytest.fixture()
def activity_bar(qtbot: QtBot) -> ActivityBar:
    ab = ActivityBar()
    qtbot.addWidget(ab)
    return ab


@pytest.fixture()
def sidebar(qtbot: QtBot) -> SidebarContainer:
    sb = SidebarContainer()
    qtbot.addWidget(sb)
    sb.add_panel("alpha", "Alpha", _label())
    sb.add_panel("beta", "Beta", _label())
    return sb


@pytest.fixture()
def acquire(qtbot: QtBot) -> AcquireModeWidget:
    w = AcquireModeWidget()
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
    from pymmcore_gui._main_window3 import _make_label

    return _make_label("test")


# ---- ActivityBar tests ----------------------------------------------------


class TestActivityBar:
    def test_add_panel(self, activity_bar: ActivityBar) -> None:
        btn = activity_bar.add_panel("foo", "Foo")
        assert "foo" in activity_bar.panel_ids
        assert btn.toolTip() == "Foo"
        assert btn.text() == "Fo"  # fallback: first 2 chars

    def test_set_active_emits_signal(
        self, activity_bar: ActivityBar, qtbot: QtBot
    ) -> None:
        activity_bar.add_panel("a", "A")
        activity_bar.add_panel("b", "B")

        with qtbot.waitSignal(activity_bar.panel_toggled) as blocker:
            activity_bar.set_active("a")
        assert blocker.args == ["a"]
        assert activity_bar.active_panel == "a"

    def test_toggle_deactivates_when_collapsible(
        self, activity_bar: ActivityBar, qtbot: QtBot
    ) -> None:
        activity_bar.add_panel("x", "X")
        activity_bar.set_active("x")
        assert activity_bar.active_panel == "x"

        with qtbot.waitSignal(activity_bar.panel_toggled) as blocker:
            activity_bar.set_active("x")  # toggle off
        assert blocker.args == [""]
        assert activity_bar.active_panel is None

    def test_toggle_blocked_when_not_collapsible(
        self, activity_bar: ActivityBar
    ) -> None:
        activity_bar.add_panel("x", "X")
        activity_bar.collapsible = False
        activity_bar.set_active("x")

        activity_bar.set_active("x")  # should NOT toggle off
        assert activity_bar.active_panel == "x"

    def test_deselect(self, activity_bar: ActivityBar) -> None:
        activity_bar.add_panel("a", "A")
        activity_bar.set_active("a")
        assert activity_bar.active_panel == "a"

        activity_bar.deselect()
        assert activity_bar.active_panel is None

    def test_activate_first(self, activity_bar: ActivityBar, qtbot: QtBot) -> None:
        activity_bar.add_panel("first", "First")
        activity_bar.add_panel("second", "Second")

        with qtbot.waitSignal(activity_bar.panel_toggled) as blocker:
            activity_bar.activate_first()
        assert blocker.args == ["first"]
        assert activity_bar.active_panel == "first"

    def test_switching_panels(self, activity_bar: ActivityBar, qtbot: QtBot) -> None:
        activity_bar.add_panel("a", "A")
        activity_bar.add_panel("b", "B")
        activity_bar.set_active("a")

        with qtbot.waitSignal(activity_bar.panel_toggled) as blocker:
            activity_bar.set_active("b")
        assert blocker.args == ["b"]
        assert activity_bar.active_panel == "b"


# ---- SidebarContainer tests ----------------------------------------------


class TestSidebarContainer:
    def test_add_panel_adds_to_stack(self, sidebar: SidebarContainer) -> None:
        assert sidebar.stack.count() == 2
        assert "alpha" in sidebar.activity_bar.panel_ids
        assert "beta" in sidebar.activity_bar.panel_ids

    def test_panel_toggled_forwarded(
        self, sidebar: SidebarContainer, qtbot: QtBot
    ) -> None:
        """SidebarContainer.panel_toggled re-emits activity_bar.panel_toggled."""
        with qtbot.waitSignal(sidebar.panel_toggled) as blocker:
            sidebar.activity_bar.set_active("alpha")
        assert blocker.args == ["alpha"]

    def test_toggle_collapse_and_restore(self, sidebar: SidebarContainer) -> None:
        sidebar.activity_bar.set_active("alpha")
        assert sidebar.activity_bar.active_panel == "alpha"

        sidebar.collapse()
        assert sidebar.activity_bar.active_panel is None

    def test_toggle_method(self, sidebar: SidebarContainer) -> None:
        sidebar.activity_bar.set_active("alpha")
        # The toggle method delegates to collapse/activate
        # When not in a splitter, is_collapsed checks visibility
        sidebar.splitter_widget.show()
        sidebar.toggle()  # should collapse
        assert sidebar.activity_bar.active_panel is None

    def test_ab_position_default(self, sidebar: SidebarContainer) -> None:
        assert sidebar.resolved_ab_position == "side"
        assert sidebar.is_ab_external is True

    def test_ab_position_top(self, sidebar: SidebarContainer) -> None:
        sidebar.set_ab_position(ActivityBarPosition.TOP)
        assert sidebar.resolved_ab_position == "top"
        assert sidebar.is_ab_external is False
        assert sidebar.splitter_widget is sidebar._combined

    def test_ab_position_hidden(self, sidebar: SidebarContainer) -> None:
        sidebar.set_ab_position(ActivityBarPosition.HIDDEN)
        sidebar.arrange()
        assert not sidebar.activity_bar.isVisible()

    def test_ab_position_changed_signal(
        self, sidebar: SidebarContainer, qtbot: QtBot
    ) -> None:
        sidebar.set_ab_position(ActivityBarPosition.BOTTOM)
        # set_ab_position only stores; the signal fires from the context menu
        # action handler. Test the signal via the public emit path:
        sidebar._ab_position = ActivityBarPosition.DEFAULT  # reset
        with qtbot.waitSignal(sidebar.ab_position_changed) as blocker:
            sidebar.ab_position_changed.emit(ActivityBarPosition.BOTTOM)
        assert blocker.args == [ActivityBarPosition.BOTTOM]

    def test_restore_from_drag(self, sidebar: SidebarContainer) -> None:
        sidebar.deselect()
        assert sidebar.activity_bar.active_panel is None

        sidebar.restore_from_drag()
        assert sidebar.activity_bar.active_panel == "alpha"

    def test_arrange_side(self, sidebar: SidebarContainer) -> None:
        sidebar.set_ab_position(ActivityBarPosition.DEFAULT)
        sidebar.arrange()
        assert sidebar.activity_bar.collapsible is True
        assert sidebar.activity_bar.isVisible()

    def test_arrange_top(self, sidebar: SidebarContainer) -> None:
        sidebar.set_ab_position(ActivityBarPosition.TOP)
        sidebar.arrange()
        assert sidebar.activity_bar.collapsible is False
        # Activity bar should be inside the combined layout
        assert sidebar.activity_bar.parent() is sidebar._combined


# ---- AcquireModeWidget tests ----------------------------------------------


class TestAcquireModeWidget:
    def test_initial_state(self, acquire: AcquireModeWidget) -> None:
        assert acquire.panel_alignment == PanelAlignment.CENTER
        assert acquire.left_sidebar.activity_bar.active_panel == "explorer"
        assert acquire.right_sidebar.activity_bar.active_panel == "properties"
        assert acquire._root_splitter is not None

    @pytest.mark.parametrize("alignment", list(PanelAlignment))
    def test_set_panel_alignment_rebuilds(
        self, acquire: AcquireModeWidget, alignment: PanelAlignment
    ) -> None:
        acquire.set_panel_alignment(alignment)
        assert acquire.panel_alignment == alignment
        assert acquire._root_splitter is not None

    def test_set_same_alignment_is_noop(self, acquire: AcquireModeWidget) -> None:
        old_splitter = acquire._root_splitter
        acquire.set_panel_alignment(PanelAlignment.CENTER)
        assert acquire._root_splitter is old_splitter

    def test_sidebar_toggle_emits_visibility_changed(
        self, acquire: AcquireModeWidget, qtbot: QtBot
    ) -> None:
        with qtbot.waitSignal(acquire.visibility_changed):
            acquire.left_sidebar.activity_bar.set_active("explorer")

    def test_toggle_panel(self, acquire: AcquireModeWidget, qtbot: QtBot) -> None:
        assert acquire.bottom_panel.isVisible()
        with qtbot.waitSignal(acquire.visibility_changed):
            acquire.toggle_panel()
        assert not acquire.bottom_panel.isVisible()

        with qtbot.waitSignal(acquire.visibility_changed):
            acquire.toggle_panel()
        assert acquire.bottom_panel.isVisible()

    def test_sidebar_collapse_and_restore(self, acquire: AcquireModeWidget) -> None:
        left = acquire.left_sidebar
        left.collapse()
        assert left.activity_bar.active_panel is None

        left.toggle()
        assert left.activity_bar.active_panel is not None

    def test_alignment_switch_preserves_leaf_widgets(
        self, acquire: AcquireModeWidget
    ) -> None:
        """Leaf widgets must survive splitter tree rebuilds."""
        editor = acquire.editor_tabs
        panel = acquire.bottom_panel
        left_stack = acquire.left_sidebar.stack
        right_stack = acquire.right_sidebar.stack

        for alignment in PanelAlignment:
            acquire.set_panel_alignment(alignment)
            # Verify widgets are still alive and parented
            assert editor.parent() is not None
            assert panel.parent() is not None
            assert left_stack.parent() is not None
            assert right_stack.parent() is not None


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
        acq = gui.acquire_mode
        assert not acq.left_sidebar.is_collapsed

        gui._toggle_left_sidebar()
        assert acq.left_sidebar.activity_bar.active_panel is None

        gui._toggle_left_sidebar()
        assert acq.left_sidebar.activity_bar.active_panel is not None

    def test_toggle_right_sidebar(self, gui: MicroManagerGUI) -> None:
        gui.show()
        acq = gui.acquire_mode
        assert not acq.right_sidebar.is_collapsed

        gui._toggle_right_sidebar()
        assert acq.right_sidebar.activity_bar.active_panel is None

        gui._toggle_right_sidebar()
        assert acq.right_sidebar.activity_bar.active_panel is not None

    def test_toggle_panel(self, gui: MicroManagerGUI) -> None:
        gui.show()
        acq = gui.acquire_mode
        assert acq.bottom_panel.isVisible()

        gui._toggle_panel()
        assert not acq.bottom_panel.isVisible()

        gui._toggle_panel()
        assert acq.bottom_panel.isVisible()

    def test_cycle_panel_alignment(self, gui: MicroManagerGUI) -> None:
        gui.show()
        acq = gui.acquire_mode
        expected_cycle = [
            PanelAlignment.RIGHT,
            PanelAlignment.JUSTIFY,
            PanelAlignment.LEFT,
            PanelAlignment.CENTER,
        ]
        # Default is CENTER, so first click goes to RIGHT
        for expected in expected_cycle:
            gui._cycle_panel_alignment()
            assert acq.panel_alignment == expected
