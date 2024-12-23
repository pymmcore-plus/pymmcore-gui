from __future__ import annotations

import traceback
from functools import cache, cached_property
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pymmcore_gui import _app

from ._code_syntax_highlight import CodeSyntaxHighlight

if TYPE_CHECKING:
    from types import TracebackType
    from typing import TypeAlias

    ExcInfo: TypeAlias = tuple[type[BaseException], BaseException, TracebackType | None]

MONO = "Menlo, Courier New, Monaco, Consolas, Andale Mono, Source Code Pro, monospace"
DEFAULT_THEME = "default"


@cache
def _format_exception(exc_info: ExcInfo) -> str:
    """Format the exception details."""
    exc_type, exc_value, exc_traceback = exc_info
    details = f"{exc_type.__name__}: {exc_value}\n\n"
    if exc_traceback:
        details += "".join(traceback.format_tb(exc_traceback))
    return details


class ExceptionLog(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Exception Explorer")

        self.exception_log = _app.EXCEPTION_LOG

        # Top: Filter and Copy
        self._type_combo = QComboBox()
        self._type_combo.addItem("All")
        self._type_combo.currentTextChanged.connect(self._refresh_exc_list)

        self._text_search = QLineEdit()
        self._text_search.setPlaceholderText("Search")
        self._text_search.setClearButtonEnabled(True)
        self._text_search.textChanged.connect(self._refresh_exc_list)

        self._copy_btn = QPushButton("Copy to Clipboard")
        self._copy_btn.clicked.connect(self.copy_to_clipboard)

        # Middle: Exception List
        self._list_wdg = QListWidget()
        self._list_wdg.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list_wdg.currentRowChanged.connect(self._on_current_row_changed)

        # Bottom: Exception Details
        self._traceback_area = txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setFont(QFont(MONO))
        self._highlight = CodeSyntaxHighlight(txt, "pytb", DEFAULT_THEME)

        self._style_combo = QComboBox()
        self._style_combo.currentTextChanged.connect(self._update_style)
        self._style_combo.addItems(
            [
                "colorful",
                "default",
                "friendly",
                "solarized-light",
                "dracula",
                "gruvbox-dark",
                "one-dark",
                "solarized-dark",
            ]
        )
        self._style_combo.insertSeparator(4)
        self._style_combo.setCurrentText(DEFAULT_THEME)

        # LAYOUT

        control_layout = QHBoxLayout()
        control_layout.addWidget(QLabel("Error Type:"), 0)
        control_layout.addWidget(self._type_combo, 1)
        control_layout.addWidget(QLabel("Search:"), 0)
        control_layout.addWidget(self._text_search, 1)

        style_layout = QHBoxLayout()
        style_layout.addStretch()
        style_layout.addWidget(QLabel("Style:"))
        style_layout.addWidget(self._style_combo)
        style_layout.addWidget(self._copy_btn)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._list_wdg)
        splitter.addWidget(self._traceback_area)

        layout = QVBoxLayout(self)
        layout.addLayout(control_layout)
        layout.addWidget(splitter)
        layout.addLayout(style_layout)
        self.resize(800, 600)

        self._refresh()

        if app := QApplication.instance():
            # support for live updates
            if hasattr(app, "exceptionRaised"):
                app.exceptionRaised.connect(self._refresh)

    def _refresh(self) -> None:
        """Add a new exception to the log."""
        self._update_filter_combo()
        self._refresh_exc_list()

    def _update_style(self) -> None:
        self._highlight.setTheme(self._style_combo.currentText())

    def _update_filter_combo(self) -> None:
        """Update the filter combo with the latest exception types."""
        prev_text = self._type_combo.currentText()
        self._type_combo.blockSignals(True)
        try:
            self._type_combo.clear()
            self._type_combo.addItem("All")
            items = {x[0].__name__ for x in self.exception_log}
            self._type_combo.addItems(sorted(items))
            if prev_text in items:
                self._type_combo.setCurrentText(prev_text)
        finally:
            self._type_combo.blockSignals(False)

    @cached_property
    def filtered_exceptions(self) -> list[ExcInfo]:
        """Filter exceptions based on the selected type."""
        etype = self._type_combo.currentText()
        exceptions = (
            self.exception_log
            if etype == "All"
            else (exc for exc in self.exception_log if exc[0].__name__ == etype)
        )
        out = []
        if text := self._text_search.text():
            splits = text.lower().split()
            for exc in exceptions:
                formatted = _format_exception(exc).lower()
                if all(x in formatted for x in splits):
                    out.append(exc)
        else:
            out = list(exceptions)
        return out

    def _refresh_exc_list(self) -> None:
        """Populate the QListWidget with filtered exceptions."""
        if hasattr(self, "filtered_exceptions"):
            del self.filtered_exceptions

        self._list_wdg.clear()
        for exc_type, exc_value, _ in self.filtered_exceptions:
            self._list_wdg.addItem(f"{exc_type.__name__}: {exc_value}")
        self._list_wdg.setCurrentRow(0)

    def _on_current_row_changed(self, index: int) -> None:
        """Display details of the selected exception."""
        text_area = self._traceback_area
        if index == -1 or index >= len(self.filtered_exceptions):
            text_area.clear()
            self._copy_btn.setEnabled(False)
            return

        details = _format_exception(self.filtered_exceptions[index])
        text_area.setText(details)
        text_area.moveCursor(QTextCursor.MoveOperation.Start)
        self._copy_btn.setEnabled(True)

    def copy_to_clipboard(self) -> None:
        """Copy the selected exception to the clipboard."""
        if clipboard := QApplication.clipboard():
            details = self._traceback_area.toPlainText()
            clipboard.setText(details)
