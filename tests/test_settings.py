from pymmcore_gui.settings import SettingsV1


def test_settings() -> None:
    settings = SettingsV1()
    assert settings.version == "1.0"

    # settings ignores unrecognized fields
    # (this is important for backwards compatibility)
    v = SettingsV1(random_value="asdf")
    assert not hasattr(v, "random_value")
