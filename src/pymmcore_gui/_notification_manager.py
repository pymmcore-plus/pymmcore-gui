from __future__ import annotations

import time
from dataclasses import dataclass, field
from itertools import count
from typing import TYPE_CHECKING, Literal, TypeAlias

from PyQt6.QtCore import QEvent, QObject, QPoint, pyqtSignal
from PyQt6.QtWidgets import QWidget

from .widgets._notifications import NotificationToast

if TYPE_CHECKING:
    from collections.abc import Callable

    NotificationSeverity: TypeAlias = Literal["info", "warning", "error"]

_id_counter = count()


@dataclass
class Notification:
    message: str
    severity: NotificationSeverity = "info"
    actions: tuple[str, ...] = field(default_factory=tuple)
    on_action: Callable[[str | None], None] | None = None
    # Currently, only 2 kinds of notifications are sticky:
    #   - Error notifications with primary actions
    #   - Notifications that show progress
    sticky: bool = False  # don't remove after timeout
    # default: visible unless do-not-disturb is on
    # silent: only visible from notifications panel
    # urgent: visible even in do-not-disturb mode
    priority: Literal["default", "silent", "urgent"] = "default"
    # id used to persist the selection of not showing again
    never_show_again: str | None = None
    timestamp: float = field(default_factory=time.time, init=False)
    id: int = field(default_factory=lambda: next(_id_counter), init=False)
    # progress: float | None = None


class NotificationManager(QObject):
    notificationAdded = pyqtSignal(Notification)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._notifications: list[Notification] = []
        self._notification_widgets: list[NotificationToast] = []
        parent.installEventFilter(self)

    def show_info_message(
        self,
        message: str,
        *actions: str,
        # callable that receives the selected item, or None if notification is dismissed
        on_action: Callable[[str | None], None] | None = None,
    ) -> None:
        notification = Notification(
            message, severity="info", actions=actions, on_action=on_action
        )
        self._add_notification(notification)

    def show_warning_message(
        self,
        message: str,
        *actions: str,
        # callable that receives the selected item, or None if notification is dismissed
        on_action: Callable[[str | None], None] | None = None,
    ) -> None:
        notification = Notification(
            message, severity="warning", actions=actions, on_action=on_action
        )
        self._add_notification(notification)

    def show_error_message(
        self,
        message: str,
        *actions: str,
        # callable that receives the selected item, or None if notification is dismissed
        on_action: Callable[[str | None], None] | None = None,
    ) -> None:
        notification = Notification(
            message, severity="error", actions=actions, on_action=on_action
        )
        self._add_notification(notification)

    def _add_notification(self, notification: Notification) -> None:
        self._notifications.append(notification)
        self._show_notification_widget(notification)
        self.notificationAdded.emit(notification)

    def _show_notification_widget(self, notification: Notification) -> None:
        """Show a new notification toast."""
        if not isinstance(parent := self.parent(), QWidget):
            return

        widget = NotificationToast(notification, self, parent)
        self._notification_widgets.insert(0, widget)
        self.reposition_notifications(animate=True)

    def remove_widget(self, widget: NotificationToast) -> None:
        self._notification_widgets.remove(widget)
        widget.close()
        widget.deleteLater()
        self.reposition_notifications(animate=True)

    def notifications(self) -> tuple[Notification, ...]:
        return tuple(self._notifications)

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Handles parent resize/move events to reposition notifications."""
        if (
            event
            and watched == self.parent()
            and event.type() in {QEvent.Type.Resize, QEvent.Type.Move}
        ):
            self.reposition_notifications()
        return super().eventFilter(watched, event)

    def reposition_notifications(self, animate: bool = False) -> None:
        """Reposition notifications when parent resizes."""
        """Animate notifications to their new positions based on cumulative heights."""

        if not isinstance(parent := self.parent(), QWidget):
            return

        offset = 0
        spacing = 8  # Extra spacing between notifications
        parent_rect = parent.rect()
        target_x = (
            parent_rect.right()
            - NotificationToast.WIDTH
            - NotificationToast.RIGHT_MARGIN
        )
        bottom = parent_rect.bottom()
        for idx, widget in enumerate(self._notification_widgets):
            # Compute y using the cumulative offset and the widget's own height.
            target_y = bottom - offset - widget.height()
            target_pos = QPoint(target_x, target_y)
            widget.reposition(target_pos, animate=animate and bool(idx))
            offset += widget.height() + spacing
