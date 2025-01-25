from __future__ import annotations

import sys
import traceback
from functools import cache, cached_property
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor
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
from superqt.utils import CodeSyntaxHighlight

from pymmcore_gui import _app

if TYPE_CHECKING:
    from types import TracebackType
    from typing import TypeAlias

    from typing_extensions import Never

    ExcInfo: TypeAlias = tuple[type[BaseException], BaseException, TracebackType | None]

LIGHT_DEFAULT = "default"
DARK_DEFAULT = "gruvbox-dark"
THEME_OPTIONS = [
    # ---- light themes ----
    "colorful",
    "default",
    "friendly",
    "solarized-light",
    # ---- dark themes ----
    "dracula",
    "gruvbox-dark",
    "one-dark",
    "solarized-dark",
]


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

        # Top Row: Filter and Copy
        self._type_combo = QComboBox()
        self._type_combo.addItem("All")
        self._type_combo.currentTextChanged.connect(self._refresh_exc_list)

        self._text_search = QLineEdit()
        self._text_search.setPlaceholderText("Search")
        self._text_search.setClearButtonEnabled(True)
        self._text_search.textChanged.connect(self._refresh_exc_list)

        # Middle: Exception List and details
        self._list_wdg = QListWidget()
        self._list_wdg.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list_wdg.currentRowChanged.connect(self._on_current_row_changed)

        self._traceback_area = tb_area = QTextEdit()
        tb_area.setReadOnly(True)

        # Bottom: Style and Clear
        default_theme = DARK_DEFAULT if _is_dark_themed(self) else LIGHT_DEFAULT
        self._highlight = CodeSyntaxHighlight(tb_area, "pytb", default_theme)

        self._style_combo = QComboBox()
        self._style_combo.currentTextChanged.connect(self._update_style)
        self._style_combo.addItems(THEME_OPTIONS)
        self._style_combo.insertSeparator(4)
        self._style_combo.setCurrentText(default_theme)

        self._copy_btn = QPushButton("Copy to Clipboard")
        self._copy_btn.clicked.connect(self.copy_to_clipboard)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._clear)

        # LAYOUT

        top_row = QHBoxLayout()

        top_row.addWidget(QLabel("Error Type:"), 0)
        top_row.addWidget(self._type_combo, 1)
        top_row.addWidget(QLabel("Search:"), 0)
        top_row.addWidget(self._text_search, 1)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        bottom_row.addWidget(QLabel("Style:"))
        bottom_row.addWidget(self._style_combo)
        bottom_row.addWidget(self._copy_btn)
        bottom_row.addWidget(self._clear_btn)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._list_wdg)
        splitter.addWidget(self._traceback_area)

        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addWidget(splitter)
        layout.addLayout(bottom_row)
        self.resize(800, 600)

        self._refresh()

        if app := QApplication.instance():
            # support for live updates.
            if isinstance(app, _app.MMQApplication):
                app.exceptionRaised.connect(self._refresh)

        # TEST BUTTON FOR DEBUGGING --------------------

        if not getattr(sys, "frozen", False):
            raise_btn = QPushButton("TEST")
            raise_btn.clicked.connect(self._raise_exception)
            bottom_row.insertStretch(0)
            bottom_row.insertWidget(0, raise_btn)

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

    def _clear(self) -> None:
        """Clear the exception log."""
        self.exception_log.clear()
        self._refresh()

    def _raise_exception(self) -> Never:
        raise ValueError("This is a test exception.")


def _is_dark_themed(wdg: QWidget) -> bool:
    """Check if the widget is using a dark theme."""
    palette = wdg.palette()
    background_color = palette.color(wdg.backgroundRole())
    return bool(background_color.lightnessF() < 0.5)
