"""Qt chat widget for the LLM assistant."""

from __future__ import annotations

from pymmcore_gui._qt.QtCore import Qt
from pymmcore_gui._qt.QtGui import QFont, QKeyEvent
from pymmcore_gui._qt.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ._chat_backend import ChatSession


class _MessageBubble(QFrame):
    """A single message bubble (user or assistant)."""

    def __init__(
        self,
        role: str,
        text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._role = role
        self.setProperty("role", role)

        layout = QVBoxLayout(self)

        if role == "user":
            # User: bordered box, no label — like Claude Code
            self.setFrameShape(QFrame.Shape.StyledPanel)
            self.setStyleSheet(
                "_MessageBubble[role='user'] {"
                "  border: 1px solid rgba(255,255,255,0.15);"
                "  border-radius: 8px;"
                "  background: rgba(255,255,255,0.05);"
                "}"
            )
            layout.setContentsMargins(10, 8, 10, 8)
        else:
            # Assistant: no border, just content
            self.setFrameShape(QFrame.Shape.NoFrame)
            layout.setContentsMargins(4, 4, 4, 4)

        # Content
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setFrameShape(QFrame.Shape.NoFrame)
        self._browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._browser.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._browser.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._browser.document().setDocumentMargin(0)
        self._browser.document().contentsChanged.connect(self._adjust_height)
        layout.addWidget(self._browser)

        self._raw_text = ""

        if text:
            self.set_text(text)

    def set_text(self, text: str) -> None:
        self._raw_text = text
        self._render()

    def append_text(self, text: str) -> None:
        self._raw_text += text
        self._render()

    def _render(self) -> None:
        self._browser.setMarkdown(self._raw_text)
        self._adjust_height()

    def _adjust_height(self) -> None:
        doc = self._browser.document()
        # Force the document to re-layout at the current viewport width
        doc.setTextWidth(self._browser.viewport().width())
        h = int(doc.size().height()) + self._browser.contentsMargins().top() * 2
        self._browser.setFixedHeight(max(h, 20))


class _ToolCallCard(QFrame):
    """A collapsible card showing a tool call and its result."""

    def __init__(
        self,
        tool_id: str,
        tool_name: str,
        input_json: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tool_id = tool_id
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setProperty("role", "tool")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # Header row
        header = QHBoxLayout()
        self._toggle_btn = QToolButton()
        self._toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.toggled.connect(self._on_toggle)
        header.addWidget(self._toggle_btn)

        name_label = QLabel(f"Tool: {tool_name}")
        font = name_label.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() - 1)
        name_label.setFont(font)
        header.addWidget(name_label)
        header.addStretch()

        self._status_label = QLabel("running...")
        self._status_label.setStyleSheet("color: gray;")
        header.addWidget(self._status_label)
        layout.addLayout(header)

        # Detail area (collapsed by default)
        self._detail = QTextBrowser()
        self._detail.setFrameShape(QFrame.Shape.NoFrame)
        self._detail.setVisible(False)
        mono = QFont("Menlo, Consolas, monospace")
        mono.setPointSize(mono.pointSize() - 1)
        self._detail.setFont(mono)
        self._detail.setPlainText(f"Input:\n{input_json}")
        self._detail.setMaximumHeight(200)
        layout.addWidget(self._detail)

    @property
    def tool_id(self) -> str:
        return self._tool_id

    def set_result(self, content: str, is_error: bool) -> None:
        current = self._detail.toPlainText()
        self._detail.setPlainText(f"{current}\n\nResult:\n{content}")
        if is_error:
            self._status_label.setText("error")
            self._status_label.setStyleSheet("color: red;")
        else:
            self._status_label.setText("done")
            self._status_label.setStyleSheet("color: green;")

    def _on_toggle(self, checked: bool) -> None:
        self._detail.setVisible(checked)
        arrow = Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        self._toggle_btn.setArrowType(arrow)


class _ChatInput(QTextEdit):
    """Multi-line input that sends on Enter (Shift+Enter for newline)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText("Type a message...")
        self.setMaximumHeight(80)
        self.setAcceptRichText(False)
        self._send_callback: object = None

    def set_send_callback(self, cb: object) -> None:
        self._send_callback = cb

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is None:
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                if self._send_callback and callable(self._send_callback):
                    self._send_callback()
                return
        super().keyPressEvent(event)


class LLMChatWidget(QWidget):
    """Main chat widget with message display, input, and ON/OFF toggle."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session = ChatSession(self)
        self._tool_cards: dict[str, _ToolCallCard] = {}
        self._current_assistant_bubble: _MessageBubble | None = None
        self._thinking_label: QLabel | None = None

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Header ---
        header = QFrame()
        header.setFrameShape(QFrame.Shape.NoFrame)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)

        title = QLabel("Christina")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Rate limit status (hidden until first event)
        self._rate_label = QLabel()
        self._rate_label.setStyleSheet("color: gray; font-size: 10px;")
        self._rate_label.setVisible(False)
        header_layout.addWidget(self._rate_label)

        # Hardware toggle
        self._toggle = QToolButton()
        self._toggle.setCheckable(True)
        self._toggle.setChecked(True)
        self._toggle.setText("Hardware Enabled")
        self._toggle.setToolTip("Toggle hardware control")
        self._toggle.toggled.connect(self._on_toggle)
        self._update_toggle_style(True)
        header_layout.addWidget(self._toggle)

        main_layout.addWidget(header)

        # --- Separator ---
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(sep)

        # --- Message scroll area ---
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._messages_container = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_container)
        self._messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._messages_layout.setSpacing(6)
        self._messages_layout.setContentsMargins(6, 6, 6, 6)
        self._messages_layout.addStretch()

        self._scroll.setWidget(self._messages_container)
        main_layout.addWidget(self._scroll, stretch=1)

        # --- Input area ---
        input_frame = QFrame()
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(6, 4, 6, 4)

        self._input = _ChatInput()
        self._input.set_send_callback(self._on_send)
        input_layout.addWidget(self._input, stretch=1)

        self._send_btn = QPushButton("Send")
        self._send_btn.setFixedWidth(60)
        self._send_btn.clicked.connect(self._on_send)
        self._send_btn.setEnabled(False)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setFixedWidth(60)
        self._stop_btn.clicked.connect(self._on_stop)
        self._stop_btn.setVisible(False)

        input_layout.addWidget(self._send_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        input_layout.addWidget(self._stop_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        main_layout.addWidget(input_frame)

    def _connect_signals(self) -> None:
        s = self._session
        s.session_ready.connect(self._on_session_ready)
        s.text_received.connect(self._on_text_received)
        s.tool_use_started.connect(self._on_tool_use)
        s.tool_result_received.connect(self._on_tool_result)
        s.response_finished.connect(self._on_response_finished)
        s.error_occurred.connect(self._on_error)
        s.rate_limit_updated.connect(self._on_rate_limit)

    # ------------------------------------------------------------------
    # Widget lifecycle
    # ------------------------------------------------------------------

    def showEvent(self, event: object) -> None:
        super().showEvent(event)  # type: ignore[arg-type]
        self._session.start_session()

    def hideEvent(self, event: object) -> None:
        super().hideEvent(event)  # type: ignore[arg-type]
        # Keep session alive when hidden so context is preserved

    def closeEvent(self, event: object) -> None:
        self._session.stop_session()
        super().closeEvent(event)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_session_ready(self) -> None:
        self._send_btn.setEnabled(True)
        self._add_system_message("Christina is ready. How can I help?")

    def _on_send(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._input.clear()
        self._add_user_message(text)
        self._current_assistant_bubble = None
        self._set_responding(True)
        self._show_thinking()
        self._session.send_message(text)

    def _on_stop(self) -> None:
        self._session.interrupt()
        self._add_system_message("Interrupted. What should Christina do next?")
        self._set_responding(False)

    def _on_text_received(self, text: str) -> None:
        self._hide_thinking()
        if self._current_assistant_bubble is None:
            self._current_assistant_bubble = self._add_assistant_message("")
        self._current_assistant_bubble.append_text(text)
        self._scroll_to_bottom()

    def _on_tool_use(self, tool_id: str, name: str, input_json: str) -> None:
        self._hide_thinking()
        # New text bubble will be needed after tool calls
        self._current_assistant_bubble = None
        card = _ToolCallCard(tool_id, name, input_json)
        self._tool_cards[tool_id] = card
        # Insert before the stretch at the end
        idx = self._messages_layout.count() - 1
        self._messages_layout.insertWidget(idx, card)
        self._scroll_to_bottom()

    def _on_tool_result(self, tool_id: str, content: str, is_error: bool) -> None:
        if card := self._tool_cards.get(tool_id):
            card.set_result(content, is_error)

    def _on_response_finished(self) -> None:
        self._current_assistant_bubble = None
        self._set_responding(False)

    def _on_error(self, message: str) -> None:
        self._add_system_message(f"Error: {message}")
        self._set_responding(False)

    def _on_rate_limit(self, info: dict) -> None:
        from datetime import datetime, timezone

        status = info.get("status", "unknown")
        resets_at = info.get("resetsAt")
        is_overage = info.get("isUsingOverage", False)

        if status != "allowed":
            self._rate_label.setStyleSheet("color: orange; font-size: 10px;")
            self._rate_label.setText("rate limited")
        elif is_overage:
            self._rate_label.setStyleSheet("color: orange; font-size: 10px;")
            self._rate_label.setText("overage")
        else:
            self._rate_label.setStyleSheet("color: gray; font-size: 10px;")
            if resets_at:
                dt = datetime.fromtimestamp(resets_at, tz=timezone.utc)
                self._rate_label.setText(f"resets {dt:%H:%M} UTC")
            else:
                self._rate_label.setText("")
        self._rate_label.setVisible(bool(self._rate_label.text()))

    def _on_toggle(self, checked: bool) -> None:
        self._update_toggle_style(checked)
        self._session.set_hardware_enabled(checked)
        state = "enabled" if checked else "disabled"
        self._add_system_message(f"Hardware {state}.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_responding(self, responding: bool) -> None:
        """Toggle between send/stop buttons based on response state."""
        self._send_btn.setVisible(not responding)
        self._send_btn.setEnabled(not responding)
        self._stop_btn.setVisible(responding)
        if not responding:
            self._hide_thinking()
            self._input.setFocus()

    def _show_thinking(self) -> None:
        self._hide_thinking()
        self._thinking_label = QLabel("Thinking...")
        self._thinking_label.setStyleSheet(
            "color: rgba(255,255,255,0.4); font-style: italic; padding: 4px 8px;"
        )
        idx = self._messages_layout.count() - 1
        self._messages_layout.insertWidget(idx, self._thinking_label)
        self._scroll_to_bottom()

    def _hide_thinking(self) -> None:
        if self._thinking_label is not None:
            self._thinking_label.setParent(None)
            self._thinking_label.deleteLater()
            self._thinking_label = None

    def _update_toggle_style(self, enabled: bool) -> None:
        if enabled:
            self._toggle.setText("Hardware Enabled")
            self._toggle.setStyleSheet(
                "QToolButton { background-color: #2d8a4e; color: white; "
                "border-radius: 4px; padding: 2px 8px; }"
            )
        else:
            self._toggle.setText("Hardware Disabled")
            self._toggle.setStyleSheet(
                "QToolButton { background-color: #6e3630; color: white; "
                "border-radius: 4px; padding: 2px 8px; }"
            )

    def _add_user_message(self, text: str) -> _MessageBubble:
        bubble = _MessageBubble("user", text)
        idx = self._messages_layout.count() - 1
        self._messages_layout.insertWidget(idx, bubble)
        self._scroll_to_bottom()
        return bubble

    def _add_assistant_message(self, text: str) -> _MessageBubble:
        bubble = _MessageBubble("assistant", text)
        idx = self._messages_layout.count() - 1
        self._messages_layout.insertWidget(idx, bubble)
        self._scroll_to_bottom()
        return bubble

    def _add_system_message(self, text: str) -> None:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: gray; font-style: italic; padding: 4px;")
        idx = self._messages_layout.count() - 1
        self._messages_layout.insertWidget(idx, label)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        QApplication.processEvents()
        sb = self._scroll.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())
