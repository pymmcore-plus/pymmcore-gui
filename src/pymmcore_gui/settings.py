import json
import warnings
from pathlib import Path
from typing import Any, Literal

from platformdirs import user_data_dir
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

APP_NAME = "pymmcore-gui"
USER_DATA_DIR = Path(user_data_dir(appname=APP_NAME))


class MMGuiSettingsSource(PydanticBaseSettingsSource):
    """Loads variables from file json file persisted to disk."""

    FILE = USER_DATA_DIR / "settings.json"

    @staticmethod
    def exists() -> bool:
        """Return True if the settings file exists."""
        return MMGuiSettingsSource.FILE.exists()

    @staticmethod
    def content() -> str:
        """Return the contents of the settings file."""
        return MMGuiSettingsSource.FILE.read_text(errors="ignore")

    @staticmethod
    def values() -> dict[str, Any]:
        """Return the contents of the settings file."""
        if not MMGuiSettingsSource.exists():
            return {}

        if not (content := MMGuiSettingsSource.content()):
            # file exists but is empty
            return {}

        values = json.loads(content)
        if not isinstance(values, dict):
            raise ValueError("Settings file does not contain a dictionary.")

        return values

    def _read_settings(self) -> dict[str, Any]:
        """Return the settings values from the source."""
        try:
            return MMGuiSettingsSource.values()
        except Exception as e:
            # Never block the application from starting because of a settings file
            warnings.warn(
                f"Failed to read settings from {MMGuiSettingsSource.FILE}: {e}",
                RuntimeWarning,
                stacklevel=2,
            )
        return {}

    def __call__(self) -> dict[str, Any]:
        """Return Settings values for this source."""
        return self._read_settings()

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        """Return the value for a field (required by ABC)."""
        # Nothing to do here. Only implement the return statement to make mypy happy
        return None, "", False


class SettingsV1(BaseSettings):
    """Global settings for the PyMMCore GUI."""

    version: Literal["1.0"] = "1.0"

    # ----------------------- Configurations -----------------------

    model_config = SettingsConfigDict(
        # Prefix for all environment variables. e.g. PMM_<key>=<value>
        env_prefix="PMM_",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Define the sources and their order for loading the settings values.

        Values are loaded in the order of the sources. Priority is given to earlier
        sources (i.e. values explicitly passed to the constructor take priority,
        then environment variables, then dotenv files, then the user settings from
        SETTINGS_FILE, then file secrets).
        """
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            MMGuiSettingsSource(settings_cls),
            file_secret_settings,
        )
