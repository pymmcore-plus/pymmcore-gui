import pytest
from PyQt6.QtWidgets import QMenu, QWidget

from pymmcore_gui import MicroManagerGUI
from pymmcore_gui.actions import ActionInfo, CoreAction, WidgetAction, WidgetActionInfo


def test_action_registry():
    info = ActionInfo.for_key(CoreAction.SNAP)
    assert info.text == "Snap Image"

    with pytest.raises(KeyError, match=f"Did you mean {CoreAction.LOAD_DEMO.value!r}?"):
        ActionInfo.for_key(CoreAction.LOAD_DEMO.value[:-2])

    with pytest.raises(TypeError, match="is not an instance of"):
        info = WidgetActionInfo.for_key(CoreAction.SNAP)
    info = WidgetActionInfo.for_key(WidgetAction.ABOUT)


@pytest.mark.usefixtures("qapp")
def test_actions_in_menus():
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
