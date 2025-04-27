from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING
from unittest.mock import patch

from pymmcore_plus import __version__
from typer.testing import CliRunner

from pymmcore_gui import _settings
from pymmcore_gui._cli import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
subrun = subprocess.run


def test_show_version() -> None:
    """show version should work."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "pymmcore-plus" in result.stdout
    assert __version__ in result.stdout


def test_settings(tmp_path: Path) -> None:
    """show version should work."""
    with patch.object(_settings, "reset_to_defaults") as mock_reset:
        result = runner.invoke(app, ["settings", "--reset"])
        assert result.exit_code == 0
        mock_reset.assert_called_once()
