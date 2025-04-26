import pytest

from pymmcore_gui.actions import ActionInfo, CoreAction
from pymmcore_gui.actions._action_info import WidgetActionInfo
from pymmcore_gui.actions.widget_actions import WidgetAction


def test_action_registry():
    info = ActionInfo.for_key(CoreAction.SNAP)
    assert info.text == "Snap Image"

    with pytest.raises(KeyError, match=f"Did you mean {CoreAction.LOAD_DEMO.value!r}?"):
        ActionInfo.for_key(CoreAction.LOAD_DEMO.value[:-2])

    with pytest.raises(TypeError, match="is not an instance of"):
        info = WidgetActionInfo.for_key(CoreAction.SNAP)

    info = WidgetActionInfo.for_key(WidgetAction.ABOUT)
    assert info in ActionInfo.widget_actions().values()
