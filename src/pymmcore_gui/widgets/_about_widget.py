import urllib.error
import urllib.request
from pathlib import Path

from pymmcore_plus._util import system_info
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import QDialog, QFormLayout, QLabel, QVBoxLayout, QWidget

from pymmcore_gui import __version__

RESOURCES = Path(__file__).parent.parent / "resources"


class AboutWidget(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # add logo
        title = QLabel("pymmcore-gui")
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))

        version = QLabel(f"v{__version__}")

        logo = QLabel()
        logo.setPixmap(QPixmap(str(RESOURCES / "logo.png")).scaled(180, 180))

        href = url = "http://github.com/pymmcore-plus/pymmcore-gui"
        if "+" in __version__:
            sha = __version__.split("+")[1]
            href = f"{url}/commit/{sha}"

            # check if the link is 404 and fallback to the main url
            try:
                urllib.request.urlopen(href)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    href = url

        link = QLabel(f"<a href={href}>{url}</a>")
        link.setTextFormat(Qt.TextFormat.RichText)
        link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        link.setOpenExternalLinks(True)

        form = QFormLayout()
        form.setVerticalSpacing(2)
        for key, value in system_info().items():
            if value:
                form.addRow(f"{key}:", QLabel(str(value)))

        layout = QVBoxLayout(self)
        layout.addWidget(title, 0, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(version, 0, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(logo, 0, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(link, 0, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addLayout(form)
