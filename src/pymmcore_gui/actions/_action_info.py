from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

from pymmcore_plus import CMMCorePlus
from PyQt6.QtCore import QObject
from PyQt6.QtGui import QAction

from pymmcore_gui.actions._core_qaction import QCoreAction

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any, TypeAlias

    from pymmcore_plus import CMMCorePlus
    from PyQt6.QtCore import QObject, Qt
    from PyQt6.QtGui import QAction, QIcon, QKeySequence
    from typing_extensions import Self

    from pymmcore_gui.actions.widget_actions import WidgetActionInfo

    CoreActionFunc: TypeAlias = Callable[[QCoreAction], Any]
    ActionTriggeredFunc: TypeAlias = Callable[[QCoreAction, bool], Any]


class ActionKey(str, Enum):
    """A Key representing an action in the GUI.

    This is subclassed in core_actions, widget_actions, etc. to provide a unique key
    for each action.
    """

    def __str__(self) -> str:
        """Return value as the string representation."""
        return str(self.name)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


@dataclass
class ActionInfo:
    """Information for creating a QCoreAction."""

    key: str

    text: str | None = None
    auto_repeat: bool = False
    checkable: bool = False
    checked: bool = False
    enabled: bool = True
    icon: QIcon | str | None = None
    icon_text: str | None = None
    icon_visible_in_menu: bool | None = None
    menu_role: QAction.MenuRole | None = None
    priority: QAction.Priority | None = None
    shortcut: str | QKeySequence | None = None
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

    def __post_init__(self) -> None:
        ActionInfo._registry[self.key] = self

    def mark_on_created(self, f: CoreActionFunc) -> CoreActionFunc:
        """Decorator to mark a function to call when the QAction is created."""
        self.on_created = f
        return f

    def to_qaction(
        self, mmc: CMMCorePlus, parent: QObject | None = None
    ) -> QCoreAction:
        """Create a QCoreAction from this info."""
        return self._action_cls(mmc, self, parent)

    @classmethod
    def for_key(cls, key: str) -> Self:
        """Get the ActionInfo for a given key."""
        if key not in ActionInfo._registry:
            key_type = type(key).__name__
            parent_module = __name__.rsplit(".", 1)[0]
            if key_type == "WidgetAction":
                module = f"{parent_module}.widget_actions"
            else:
                module = f"{parent_module}.core_actions"
            raise KeyError(
                f"No 'ActionInfo' has been declared for key '{key_type}.{key}'. "
                f"Please create one in {module}"
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
        from pymmcore_gui.actions.widget_actions import WidgetActionInfo

        return {
            k: v for k, v in cls._registry.items() if isinstance(v, WidgetActionInfo)
        }
