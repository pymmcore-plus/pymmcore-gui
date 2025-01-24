from pymmcore_gui.settings import Settings


def test_settings() -> None:
    settings = Settings()
    assert settings.version == "1.0"
