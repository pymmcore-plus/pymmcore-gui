from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from superqt import QIconifyIcon

from pymmcore_gui._qt.QtCore import QPoint, QPropertyAnimation, Qt, QTimer
from pymmcore_gui._qt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from pymmcore_gui._notification_manager import Notification, NotificationManager


icon = {
    "info": "",
}


class NotificationToast(QWidget):
    WIDTH = 400  # Fixed width for consistency
    MARGIN = 30  # Margin from window edges
    DURATION: float = 10  # Default duration in seconds

    def __init__(
        self,
        notification: Notification,
        manager: NotificationManager,
        parent: QWidget | None,
        index: int = 0,
    ) -> None:
        super().__init__(parent)
        self.notification = notification
        self.manager = manager
        self.index = index

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.ToolTip)
        # self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("""
            QWidget {
                background-color: #161616;
                color: #CCC;
                font-size: 14px;
                padding: 8px;
            }
            QPushButton#closeButton {
                background-color: none;
                border: none;
                background: none;
                font-size: 18px;
            }
            QPushButton#closeButton:hover {
                color: #ff5555;
            }
            QPushButton {
                background-color: #333;
                border: none;
                border-radius: 0px;
                width: 120px;
            }
            QPushButton:hover {
                background-color: #555;
                color: #fff;
            }
        """)

        self.icon = QLabel()
        if notification.severity == "warning":
            ic = QIconifyIcon("codicon:warning", color="orange")
        elif notification.severity == "error":
            ic = QIconifyIcon("codicon:error", color="red")
        else:  # info  # default
            ic = QIconifyIcon("codicon:info", color="#0af")
        self.icon.setPixmap(ic.pixmap(20, 20))

        self.message_label = QLabel(notification.message.replace(r"\n", "<br>"))
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.message_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("closeButton")
        self.close_button.setFixedSize(28, 28)
        self.close_button.clicked.connect(self.remove_notification)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)
        top_layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        top_layout.addWidget(self.message_label, 0, Qt.AlignmentFlag.AlignTop)
        top_layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)

        # Bottom row with action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        for action in notification.actions:
            button = QPushButton(action)
            button.setObjectName(action)
            button.clicked.connect(self._on_btn_clicked)
            btn_layout.addWidget(button, 0, Qt.AlignmentFlag.AlignRight)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(0)
        layout.addLayout(top_layout)
        layout.addLayout(btn_layout)

        # Set initial size and position
        self.adjustSize()
        self.setFixedWidth(self.WIDTH)

        # Animations
        self.anim_opacity = QPropertyAnimation(self, b"windowOpacity")
        self.anim_position = QPropertyAnimation(self, b"pos")
        # Fade in
        self.fade_in()

        # Auto-dismiss timer
        self.auto_hide_timer = QTimer()
        self.auto_hide_timer.setSingleShot(True)
        self.auto_hide_timer.setInterval(int(self.DURATION * 1000))
        self.auto_hide_timer.timeout.connect(self.fade_out)
        self.auto_hide_timer.start()

    def _on_btn_clicked(self) -> None:
        btn = cast("QPushButton", self.sender())
        if on_action := self.notification.on_action:
            on_action(btn.text())
            self.remove_notification()

    def reposition(self, pos: QPoint, animate: bool = False) -> None:
        """Moves the notification to the bottom-right of the parent widget."""
        if animate:
            self.anim_position.setDuration(200)
            self.anim_position.setStartValue(self.pos())
            self.anim_position.setEndValue(pos)
            self.anim_position.start()
        else:
            self.move(pos)

    def fade_in(self) -> None:
        """Fades the notification in."""
        self.setWindowOpacity(0)
        self.show()
        self.anim_opacity.setDuration(300)
        self.anim_opacity.setStartValue(0)
        self.anim_opacity.setEndValue(1)
        self.anim_opacity.start()

    def fade_out(self) -> None:
        """Fades the notification out and removes it."""
        self.anim_opacity.setDuration(500)
        self.anim_opacity.setStartValue(1)
        self.anim_opacity.setEndValue(0)
        self.anim_opacity.finished.connect(self.remove_notification)
        self.anim_opacity.start()

    def remove_notification(self) -> None:
        """Removes the notification from the manager."""
        self.manager.remove_widget(self)

    def mousePressEvent(self, a0: Any) -> None:
        """Highlight toast and cancel auto-hide on click."""
        self.auto_hide_timer.stop()  # Cancel auto-hide
