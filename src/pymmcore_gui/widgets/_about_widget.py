from pathlib import Path

from pymmcore_plus._util import system_info  # TODO: make public in pymmcore_plus
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
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

        # LOGO
        logo = QLabel()
        logo.setPixmap(QPixmap(str(RESOURCES / "logo.png")).scaled(160, 160))

        # TITLE, VERSION, LINK
        title = QLabel("pymmcore-gui")
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))

        version = QLabel(f"Version: {__version__}")

        link = QLabel(f"<a href={gh_link()}>{GH_REPO_URL}</a>")
        link.setTextFormat(Qt.TextFormat.RichText)
        link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        link.setOpenExternalLinks(True)

        # SYSTEM INFORMATION
        sys_info = system_info()
        sys_info.pop("tifffile", None)
        sys_info.pop("zarr", None)
        self._info = {"pymmcore-gui": __version__, **sys_info}

        form = QFormLayout()
        form.setVerticalSpacing(2)
        for key, value in sys_info.items():
            if value:
                form.addRow(f"{key}:", QLabel(str(value)))

        # BUTTONS
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(self.accept)
        if copy := btn_box.addButton("Copy", QDialogButtonBox.ButtonRole.ActionRole):
            copy.clicked.connect(self._copy_info)

        # LAYOUT
        title_layout = QVBoxLayout()
        title_layout.addStretch()
        title_layout.addWidget(title)
        title_layout.addWidget(version)
        title_layout.addWidget(link)
        title_layout.addStretch()

        header_layout = QHBoxLayout()
        header_layout.addStretch()
        header_layout.addWidget(logo)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(header_layout)
        layout.addLayout(form)
        layout.addWidget(btn_box)

    def _copy_info(self) -> None:
        """Copy system information to clipboard."""
        if cb := QApplication.clipboard():
            info = "\n".join(f"{key}: {value}" for key, value in self._info.items())
            cb.setText(info)
