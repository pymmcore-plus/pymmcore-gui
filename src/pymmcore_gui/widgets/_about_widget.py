from pathlib import Path

from pymmcore_plus._util import system_info  # TODO: make public in pymmcore_plus
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from pymmcore_gui import __version__
from pymmcore_gui._utils import GH_REPO_URL, gh_link

RESOURCES = Path(__file__).parent.parent / "resources"


class AboutWidget(QDialog):
    """Widget to display information about the application."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Sheet)

        # add logo
        title = QLabel("pymmcore-gui")
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))

        version = QLabel(f"v{__version__}")

        logo = QLabel()
        logo.setPixmap(QPixmap(str(RESOURCES / "logo.png")).scaled(180, 180))

        link = QLabel(f"<a href={gh_link()}>{GH_REPO_URL}</a>")
        link.setTextFormat(Qt.TextFormat.RichText)
        link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        link.setOpenExternalLinks(True)

        sys_info = system_info()
        self._info = {"pymmcore-gui": __version__, **sys_info}

        form = QFormLayout()
        form.setVerticalSpacing(2)
        for key, value in sys_info.items():
            if value:
                form.addRow(f"{key}:", QLabel(str(value)))

        # add ok, and copy buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(self.accept)
        if copy := btn_box.addButton("Copy", QDialogButtonBox.ButtonRole.ActionRole):
            copy.clicked.connect(self._copy_info)

        layout = QVBoxLayout(self)
        layout.addWidget(title, 0, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(version, 0, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(logo, 0, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(link, 0, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addLayout(form)
        layout.addWidget(btn_box)

    def _copy_info(self) -> None:
        """Copy system information to clipboard."""
        if cb := QApplication.clipboard():
            info = "\n".join(f"{key}: {value}" for key, value in self._info.items())
            cb.setText(info)
