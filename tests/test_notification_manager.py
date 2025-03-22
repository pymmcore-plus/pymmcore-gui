from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QPushButton, QWidget

from pymmcore_gui._notification_manager import Notification, NotificationManager
from pymmcore_gui.widgets._notifications import NotificationToast

if TYPE_CHECKING:
    from pytest import MonkeyPatch
    from pytestqt.qtbot import QtBot


def test_notification_manager(qtbot: QtBot, monkeypatch: MonkeyPatch) -> None:
    parent = QWidget()
    parent.show()
    nm = NotificationManager(parent)
    monkeypatch.setattr(NotificationToast, "DURATION", 0.2)

    for _i, lvl in enumerate(("info", "warning", "error")):
        msg = f"Test {lvl}"
        with qtbot.waitSignal(nm.notificationAdded, timeout=1000):
            match lvl:
                case "info":
                    nm.show_info_message(msg, "Action")
                case "warning":
                    nm.show_warning_message(msg, "Action")
                case "error":
                    nm.show_error_message(msg, "Action")

        assert isinstance((note := nm._notifications[-1]), Notification)
        assert note.message == msg
        assert note.severity == lvl
        assert note.actions == ("Action",)
        assert note.on_action is None

    # ensure that resing the parent widget calls nm.reposition_notifications:
    with patch.object(nm, "reposition_notifications") as reposition_mock:
        parent.resize(800, 600)
        reposition_mock.assert_called_once()

    # ensure clicking the Action button calls the on_action callback:
    toast = nm._notification_widgets[-1]
    assert isinstance(toast, NotificationToast)
    with qtbot.waitSignal(toast.destroyed, timeout=1000):
        ...

    action_mock = Mock()
    nm.show_info_message("info", "Action", on_action=action_mock)
    toast = nm._notification_widgets[-1]
    assert isinstance(toast, NotificationToast)
    toast.findChild(QPushButton, "Action").click()
    action_mock.assert_called_with("Action")
