import sys
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication

from pymmcore_gui import _app


def test_main_app() -> None:
    with patch.object(QApplication, "exec") as mock_exec:
        _app.main()
        assert mock_exec.called
        assert isinstance(QApplication.instance(), _app.MMQApplication)
        assert sys.excepthook == _app.ndv_excepthook
        for wdg in QApplication.topLevelWidgets():
            wdg.close()
            wdg.deleteLater()
