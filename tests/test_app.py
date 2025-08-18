import sys
from unittest.mock import patch

import pytest
from pytest import MonkeyPatch

from pymmcore_gui import __main__, _app
from pymmcore_gui._qt.QtWidgets import QApplication


@pytest.mark.order(0)
def test_main_app(monkeypatch: MonkeyPatch) -> None:
    with patch.object(
        _app.MMQApplication, "exec", lambda _: QApplication.processEvents()
    ):
        assert not QApplication.instance()
        monkeypatch.setattr(sys, "argv", ["mmgui"])
        with pytest.raises(SystemExit):
            __main__.main()

        assert QApplication.instance()
        assert isinstance(QApplication.instance(), _app.MMQApplication)
        assert hasattr(sys, "_original_excepthook_")
        for wdg in QApplication.topLevelWidgets():
            wdg.close()
