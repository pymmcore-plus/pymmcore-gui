"""Defines actions for the Help menu."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._action_info import ActionInfo, ActionKey

if TYPE_CHECKING:
    from collections.abc import Callable

    from ._core_qaction import QCoreAction


class HelpAction(ActionKey):
    """Actions for the Help menu."""

    FORUM = "pymmcore_gui.help.forum"
    REPORT_ISSUE = "pymmcore_gui.help.report_issue"
    DOCUMENTATION = "pymmcore_gui.help.documentation"


# ########################## Help Actions ######################################


def _open_url(url: str) -> Callable[[QCoreAction, bool], None]:
    def _triggered(action: QCoreAction, checked: bool) -> None:
        from pymmcore_gui._qt.QtCore import QUrl
        from pymmcore_gui._qt.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl(url))

    return _triggered


forum_action = ActionInfo(
    key=HelpAction.FORUM,
    text="Community Forum",
    icon="mdi:forum-outline",
    tooltip="Open the image.sc community forum for pymmcore",
    on_triggered=_open_url("https://forum.image.sc/tag/pymmcore/"),
)

report_issue_action = ActionInfo(
    key=HelpAction.REPORT_ISSUE,
    text="Report an Issue",
    icon="mdi:bug-outline",
    tooltip="Report a bug or request a feature on GitHub",
    on_triggered=_open_url("https://github.com/pymmcore-plus/pymmcore-gui/issues/new"),
)

documentation_action = ActionInfo(
    key=HelpAction.DOCUMENTATION,
    text="Documentation",
    icon="mdi:book-open-outline",
    tooltip="Open the pymmcore-gui documentation",
    on_triggered=_open_url("https://pymmcore-plus.github.io/pymmcore-gui/"),
)
