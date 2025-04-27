from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any, ClassVar

from pydantic import BaseModel, PlainValidator
from pymmcore_plus import CMMCorePlus
from PyQt6.QtCore import QObject, Qt  # noqa: TC002
from PyQt6.QtGui import QAction, QIcon, QKeySequence
from PyQt6Ads import CDockWidget, DockWidgetArea, SideBarLocation

from pymmcore_gui.actions._core_qaction import QCoreAction

if TYPE_CHECKING:
    from typing import TypeAlias

    from pymmcore_plus import CMMCorePlus
    from PyQt6.QtWidgets import QWidget
    from typing_extensions import Self

    from pymmcore_gui.actions.widget_actions import QWidgetType


class ActionKey(str, Enum):
    """A Key representing an action in the GUI.

    This is subclassed in core_actions, widget_actions, etc. to provide a unique key
    for each action.
    """

    def __str__(self) -> str:
        """Return value as the string representation."""
        return str(self.value)


def _ensure_isinstance(cls: type) -> PlainValidator:
    """Check if the value is an instance of the class."""

    def _check_type(value: Any) -> None:
        if not isinstance(value, cls):  # pragma: no cover
            raise TypeError(
                f"Expected {cls.__name__}, got {type(value).__name__} instead."
            )

    return PlainValidator(_check_type)


CoreActionFunc: TypeAlias = Callable[[QCoreAction], Any]
ActionTriggeredFunc: TypeAlias = Callable[[QCoreAction, bool], Any]
QIconType: TypeAlias = Annotated[QIcon, _ensure_isinstance(QIcon)]
QKeySequenceType: TypeAlias = Annotated[QKeySequence, _ensure_isinstance(QKeySequence)]


class ActionInfo(BaseModel):
    """Information for creating a QCoreAction."""

    key: str
    """A unique key to identify the action."""
    text: str
    """How the action should be displayed in the GUI."""
    auto_repeat: bool = False
    checkable: bool = False
    checked: bool = False
    enabled: bool = True
    icon: str | None | QIconType = None
    icon_text: str | None = None
    icon_visible_in_menu: bool | None = None
    menu_role: QAction.MenuRole | None = None
    priority: QAction.Priority | None = None
    shortcut: str | None | QKeySequenceType = None
    shortcut_context: Qt.ShortcutContext | None = None
    shortcut_visible_in_context_menu: bool | None = None
    status_top: str | None = None
    tooltip: str | None = None
    visible: bool = True
    whats_this: str | None = None

    # called when triggered
    on_triggered: ActionTriggeredFunc | None = None
    # called when QAction is created, can be used to connect stuff
    on_created: CoreActionFunc | None = None

    # global registry of all Action
    _registry: ClassVar[dict[str, ActionInfo]] = {}
    _action_cls: ClassVar[type[QCoreAction]] = QCoreAction

    def model_post_init(self, __context: Any) -> None:
        ActionInfo._registry[self.key] = self

    def to_qaction(
        self, mmc: CMMCorePlus, parent: QObject | None = None
    ) -> QCoreAction:
        """Create a QCoreAction from this info."""
        return self._action_cls(mmc, self, parent)

    @classmethod
    def for_key(cls, key: str) -> Self:
        """Get the ActionInfo for a given key."""
        key = str(key)
        if key not in ActionInfo._registry:
            # Find possible matches among available widget actions
            import difflib

            suggestion = ""
            if matches := difflib.get_close_matches(
                key, list(ActionInfo._registry), n=1, cutoff=0.5
            ):
                suggestion = f"\n\nDid you mean {matches[0]!r}?"

            raise KeyError(
                f"No 'ActionInfo' has been declared for key '{key}'.{suggestion}"
            )

        info = ActionInfo._registry[key]
        if not isinstance(info, cls):
            raise TypeError(
                f"ActionInfo for key {key} is not an instance of {cls!r}. "
                f"Please call `for_key` on the appropriate super-class."
            )
        return info

    @classmethod
    def widget_actions(cls) -> dict[str, WidgetActionInfo]:
        """Return all widget actions."""
        return {
            k: v for k, v in cls._registry.items() if isinstance(v, WidgetActionInfo)
        }


class WidgetActionInfo(ActionInfo):
    """Subclass to set default values for WidgetAction."""

    # by default, widget actions are checkable, and the check state indicates visibility
    checkable: bool = True
    # function that can be called with (parent: QWidget) -> QWidget
    create_widget: Callable[[QWidgetType], QWidget]
    # Use None to indicate that the widget should not be docked
    dock_area: DockWidgetArea | SideBarLocation | None = (
        DockWidgetArea.RightDockWidgetArea
    )
    scroll_mode: CDockWidget.eInsertMode = CDockWidget.eInsertMode.AutoScrollArea
