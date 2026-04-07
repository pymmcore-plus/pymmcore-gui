import pytest
import useq

from pymmcore_gui import MicroManagerGUI
from pymmcore_gui._qt.QtWidgets import QMenu, QWidget
from pymmcore_gui.actions import ActionInfo, CoreAction, WidgetAction, WidgetActionInfo


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


def test_mda_widget_status_line(qtbot) -> None:
    win = MicroManagerGUI()
    qtbot.addWidget(win)
    mda = win.get_widget(WidgetAction.MDA_WIDGET)

    def wait_status(predicate) -> str:
        qtbot.waitUntil(lambda: predicate(mda._status_label.text()))
        return mda._status_label.text()

    sequence = useq.MDASequence(
        stage_positions=[
            useq.Position(x=0.0, y=0.0, name="P1"),
            useq.Position(x=1.0, y=1.0, name="P2"),
        ],
        channels=[useq.Channel(config="DAPI")],
        time_plan=useq.TIntervalLoops(interval=0.1, loops=2),
    )
    event = next(sequence.iter_events())

    assert mda._status_label.text() == "Idle"
    mda._on_sequence_started(sequence, {})
    assert mda._frame_total == 4
    assert wait_status(lambda text: text == "Frame 0/4 | Step: Preparing")

    mda._on_event_started(event)
    status = wait_status(lambda text: text.endswith("Step: Acquiring"))
    assert "Pos 1/2" in status
    assert "T 1/2" in status
    assert "Channel DAPI" in status

    mda._on_frame_ready(object(), event, {})
    assert wait_status(lambda text: text.startswith("Frame 1/4"))

    mda._on_awaiting_event(event, 1.25)
    status = wait_status(lambda text: "Step: Waiting next frame" in text)
    assert "Next: 1.2 s" in status

    mda._on_pause_toggled(True)
    assert "Step: Paused" in wait_status(lambda text: "Step: Paused" in text)

    af_event = useq.MDAEvent(index={"p": 0}, action=useq.HardwareAutofocus())
    mda._on_event_started(af_event)
    assert "Step: Autofocus" in wait_status(lambda text: "Step: Autofocus" in text)

    mda._on_sequence_canceled(sequence)
    assert "Step: Canceled" in wait_status(lambda text: "Step: Canceled" in text)
    mda._on_sequence_finished(sequence)
    assert "Step: Canceled" in wait_status(lambda text: "Step: Canceled" in text)
