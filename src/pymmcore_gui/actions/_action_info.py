from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QAction, QIcon, QKeySequence


@dataclass
class ActionInfo:
    key: Any
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
