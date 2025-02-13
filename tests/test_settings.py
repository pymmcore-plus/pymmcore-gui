from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic_settings import BaseSettings

from pymmcore_gui.settings import MMGuiUserPrefsSource, SettingsV1


def test_settings() -> None:
    settings = SettingsV1()
    assert settings.version == "1.0"
    assert settings.version_tuple == (1, 0, "")

    # settings ignores unrecognized fields
    # (this is important for backwards compatibility)
    v = SettingsV1(random_value="asdf")  # pyright: ignore[reportCallIssue]
    assert not hasattr(v, "random_value")


def test_user_settings(tmp_path: Path) -> None:
    fake_settings = tmp_path / "settings.json"
    with patch.object(MMGuiUserPrefsSource, "FILE", fake_settings):
        assert not MMGuiUserPrefsSource.exists()
        assert MMGuiUserPrefsSource.values() == {}

        fake_settings.touch()
        assert MMGuiUserPrefsSource.exists()
        assert MMGuiUserPrefsSource(BaseSettings)() == {}

        fake_settings.write_text('{"a": 1}')
        assert MMGuiUserPrefsSource(BaseSettings)() == {"a": 1}

        fake_settings.write_text("[]")
        with pytest.warns(RuntimeWarning, match="Failed to read settings"):
            assert MMGuiUserPrefsSource(BaseSettings)() == {}
