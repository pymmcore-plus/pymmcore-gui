from PyQt6.QtGui import QTextOption
from PyQt6.QtWidgets import QTextEdit, QVBoxLayout, QWidget


class ExceptionLog(QWidget):
    """A scrolling text window with all of the exception tracebacks."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._log = QTextEdit(self)
        self._log.setReadOnly(True)
        self._log.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self._log.setWordWrapMode(QTextOption.WrapMode.NoWrap)
        self._log.setAcceptRichText(False)
        self._log.setTabChangesFocus(True)
        self._log.setTabStopDistance(4)
        self._log.setDocumentTitle("Exception Log")

        self._log.setPlaceholderText("No exceptions have been raised.")

        from pymmcore_gui._app import EXCEPTION_LOG

        for exc_ref in EXCEPTION_LOG:
            exc = exc_ref()
            if exc:
                self.append_exception(exc)

        layout = QVBoxLayout(self)
        layout.addWidget(self._log)

    def append_exception(self, exc: BaseException) -> None:
        """Append an exception to the log."""
        self._log.append(str(exc))
