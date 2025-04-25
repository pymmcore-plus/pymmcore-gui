import sys
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication
from pytest import MonkeyPatch

from pymmcore_gui import _app


def test_main_app(monkeypatch: MonkeyPatch) -> None:
    with patch.object(
        _app.MMQApplication, "exec", lambda _: QApplication.processEvents()
    ):
        assert not QApplication.instance()
        monkeypatch.setattr(sys, "argv", ["mmgui"])
        _app.create_mmgui()

        assert QApplication.instance()
        assert isinstance(QApplication.instance(), _app.MMQApplication)
        assert hasattr(sys, "_original_excepthook_")
        for wdg in QApplication.topLevelWidgets():
            wdg.close()
