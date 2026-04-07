from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any, TypeAlias, cast

import pytest
import useq

from pymmcore_gui import MicroManagerGUI
from pymmcore_gui._qt.QtWidgets import QMenu, QWidget
from pymmcore_gui.actions import ActionInfo, CoreAction, WidgetAction, WidgetActionInfo

StatusTrigger: TypeAlias = Callable[[], None]


def test_action_registry() -> None:
    info = ActionInfo.for_key(CoreAction.SNAP)
    assert info.text == "Snap Image"

    with pytest.raises(KeyError, match=f"Did you mean {CoreAction.LOAD_DEMO.value!r}?"):
        ActionInfo.for_key(CoreAction.LOAD_DEMO.value[:-2])

    with pytest.raises(TypeError, match="is not an instance of"):
        info = WidgetActionInfo.for_key(CoreAction.SNAP)
    info = WidgetActionInfo.for_key(WidgetAction.ABOUT)


@pytest.mark.usefixtures("qapp")
def test_actions_in_menus() -> None:
    # people can add new ones
    text = "My Widget!!!!"
    act = WidgetActionInfo(
        key="mywidget",
        text=text,
        icon="mdi-light:format-list-bulleted",
        create_widget=lambda p: QWidget(p),
    )
    assert "mywidget" in WidgetActionInfo._registry
    assert act in ActionInfo.widget_actions().values()

    win = MicroManagerGUI()
    mb = win.menuBar()
    assert mb
    window_menu = next(
        (m for a in mb.actions() if (m := a.menu()) and m.title() == "Window"), None
    )
    assert isinstance(window_menu, QMenu)
    assert any(a.text() == text for a in window_menu.actions())


def test_mda_widget_status_line(qtbot: Any) -> None:
    win = MicroManagerGUI()
    qtbot.addWidget(win)
    mda = cast("Any", win.get_widget(WidgetAction.MDA_WIDGET))

    def emit_status(trigger: StatusTrigger) -> str:
        with qtbot.waitSignal(mda.statusRequested) as blocker:
            trigger()
        args = cast("tuple[object, ...] | None", blocker.args)
        assert args is not None
        return str(args[0])

    sequence = useq.MDASequence(
        stage_positions=(
            useq.Position(x=0.0, y=0.0, name="P1"),
            useq.Position(x=1.0, y=1.0, name="P2"),
        ),
        channels=(useq.Channel(config="DAPI", exposure=1.0),),
        time_plan=useq.TIntervalLoops(interval=timedelta(seconds=0.1), loops=2),
    )
    event = next(sequence.iter_events())

    assert mda._status_label.text() == "Idle"
    status = emit_status(lambda: mda._on_sequence_started(sequence, {}))
    assert mda._frame_total == 4
    assert status == "Frame 0/4 | Step: Preparing"

    status = emit_status(lambda: mda._on_event_started(event))
    assert status.endswith("Step: Acquiring")
    assert "Pos 1/2" in status
    assert "T 1/2" in status
    assert "Channel DAPI" in status

    status = emit_status(lambda: mda._on_frame_ready(object(), event, {}))
    assert status.startswith("Frame 1/4")

    status = emit_status(lambda: mda._on_awaiting_event(event, 1.25))
    assert "Step: Waiting next frame" in status
    assert "Next: 1.2 s" in status

    status = emit_status(lambda: mda._on_pause_toggled(True))
    assert "Step: Paused" in status

    af_event = useq.MDAEvent(action=useq.HardwareAutofocus())
    status = emit_status(lambda: mda._on_event_started(af_event))
    assert "Step: Autofocus" in status

    status = emit_status(lambda: mda._on_sequence_canceled(sequence))
    assert "Step: Canceled" in status
    status = emit_status(lambda: mda._on_sequence_finished(sequence))
    assert "Step: Canceled" in status
