import json
import os
import threading
import warnings
from pathlib import Path
from typing import Annotated, Any, Literal, cast

from platformdirs import user_data_dir
from pydantic import (
    Base64Bytes,
    BaseModel,
    Field,
    TypeAdapter,
    ValidationError,
    WrapSerializer,
    model_validator,
)
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from pymmcore_gui.actions.widget_actions import WidgetAction

APP_NAME = "pymmcore-gui"
USER_DATA_DIR = Path(user_data_dir(appname=APP_NAME))
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE_NAME = USER_DATA_DIR / "pmm_settings.json"
TESTING = "PYTEST_VERSION" in os.environ
_GLOBAL_SETTINGS: "None | SettingsV1" = None


class BaseMMSettings(BaseSettings):
    """Config shared across all settings subclasses."""

    model_config = SettingsConfigDict(
        # don't fail if an extra key is present.  just ignore it
        # (this is important for backwards compatibility)
        # note: this could also be "include", if we want an older version of the app
        # to be able to open a newer version's settings file, without losing data
        extra="ignore",
    )


class MMGuiUserPrefsSource(PydanticBaseSettingsSource):
    """Loads variables from file json file persisted to disk."""

    @staticmethod
    def exists() -> bool:
        """Return True if the settings file exists."""
        return SETTINGS_FILE_NAME.exists()

    @staticmethod
    def content() -> str:
        """Return the contents of the settings file."""
        return SETTINGS_FILE_NAME.read_text(errors="ignore")

    @staticmethod
    def values() -> dict[str, Any]:
        """Return the contents of the settings file."""
        if not MMGuiUserPrefsSource.exists():
            return {}

        if not (content := MMGuiUserPrefsSource.content()):
            # file exists but is empty
            return {}

        values = json.loads(content)
        if not isinstance(values, dict):
            raise ValueError("Settings file does not contain a dictionary.")
        return values

    def _read_settings(self) -> dict[str, Any]:
        """Return the settings values from the source."""
        try:
            return MMGuiUserPrefsSource.values()
        except Exception as e:
            # Never block the application from starting because of a settings file
            warnings.warn(
                f"Failed to read settings from {SETTINGS_FILE_NAME}: {e}",
                RuntimeWarning,
                stacklevel=2,
            )
        return {}

    def __call__(self) -> dict[str, Any]:
        """Return Settings values for this source."""
        if os.getenv("MMGUI_NO_SETTINGS"):  # pragma: no cover
            return {}
        values = self._read_settings()
        return _good_data_only(SettingsV1, values, warn=True)

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        """Return the value for a field (required by ABC)."""
        # Nothing to do here. Only implement the return statement to make mypy happy
        return None, "", False  # pragma: no cover


def _good_data_only(
    cls: type[BaseModel], data: dict[str, Any], warn: bool = True
) -> dict[str, Any]:
    """Attempt to extract only the good fields from `data` that are valid for `cls`."""
    cleaned: dict[str, Any] = {}
    model_fields = cls.model_fields
    for key, value in data.items():
        if key in model_fields:
            # check whether the value is valid for the field
            field = model_fields[key]
            annotation = field.annotation
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                cleaned[key] = _good_data_only(annotation, value, warn=warn)
            else:
                try:
                    TypeAdapter(field.annotation).validate_python(value)
                    cleaned[key] = value
                except ValidationError as e:
                    if warn:
                        warnings.warn(
                            f"Could not validate key {key!r} from settings file: {e}",
                            RuntimeWarning,
                            stacklevel=2,
                        )
        elif warn:
            # user supplied something that doesn't exist in the model
            # ignore it, but warn the user
            warnings.warn(
                f"Key {key!r} from settings file not found in model.",
                RuntimeWarning,
                stacklevel=2,
            )
            # we still include it for backwards compatibility
            # it could be an additional function that "cleans" settings.
            cleaned[key] = value
    return cleaned


def _default_widgets() -> set[str]:
    """The default set widgets that open on launch."""
    return {WidgetAction.CONFIG_GROUPS, WidgetAction.MDA_WIDGET}


# set of widgets that are sorted when serialized
WidgetNames = Annotated[set[str], WrapSerializer(lambda v, h: sorted(h(v)))]


class WindowSettingsV1(BaseMMSettings):
    """Settings related to window positioning and geometry."""

    geometry: Base64Bytes | None = None
    """Position and size of the main window. Restored with .restoreGeometry()"""
    window_state: Base64Bytes | None = None
    """State of main window's toolbars and dockwidgets. Restored with .restoreState()"""
    dock_manager_state: Base64Bytes | None = None
    """State of dock_manager dockwidgets"""
    open_widgets: WidgetNames = Field(default_factory=_default_widgets)
    """Set of widgets to load on startup, or when restoring settings."""

    @model_validator(mode="before")
    @classmethod
    def _migrate_names(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Migrate old settings to new ones.

        This is a temporary solution until we have a proper migration system.
        """
        # migrate from old settings
        if "initial_widgets" in values:
            values["open_widgets"] = values.pop("initial_widgets")
        return values


class SettingsV1(BaseMMSettings):
    """Global settings for the PyMMCore GUI."""

    model_config = SettingsConfigDict(
        # Prefix for all environment variables. e.g. PMM_<key>=<value>
        env_prefix="PMM_",
    )

    version: Literal["1.0"] = "1.0"
    window: WindowSettingsV1 = Field(default_factory=WindowSettingsV1)

    send_error_reports: bool | None = None
    """Whether to send error reports to the developers, None means undecided."""

    last_config: Path | None = None
    """Path to the last used config file."""
    auto_load_last_config: bool | None = None
    """Load the last used config on startup. None means undecided."""
    fallback_to_demo_config: bool = False
    """Load demo config if no config is found."""

    @property
    def version_tuple(self) -> tuple[int, int, str]:
        """Return the version as a tuple of integers.

        The first two are guaranteed to be integers.  Any additional parts are joined
        with a period and returned as a string.
        """
        major, minor, *rest = self.version.split(".")
        return int(major), int(minor), ".".join(rest)

    # ----------------------- Configurations -----------------------

    @classmethod
    def instance(cls) -> "SettingsV1":
        """Return the singleton instance of the settings."""
        global _GLOBAL_SETTINGS
        if _GLOBAL_SETTINGS is None:
            _GLOBAL_SETTINGS = SettingsV1()
        return _GLOBAL_SETTINGS

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
        if TESTING:
            # we're running in tests...
            # don't load the user settings, and change env-prefix
            # I started by using a fixture in conftest.py, to patch this method
            # but it's difficult to ensure that it always gets patched in time
            # this is more guaranteed to work
            cast("EnvSettingsSource", env_settings).env_prefix = "PMM_TEST_"
            return (init_settings, env_settings)

        return (
            init_settings,
            env_settings,
            dotenv_settings,
            MMGuiUserPrefsSource(settings_cls),
            file_secret_settings,
        )

    def flush(self, timeout: float | None = None) -> None:
        """Write the settings to disk.

        If `timeout` is not None, block until the write is complete, or until the
        timeout is reached.
        """
        if TESTING or os.getenv("MMGUI_NO_SETTINGS"):  # pragma: no cover
            return
        # write in another thread, so we don't block the main thread
        thread = threading.Thread(target=self._write_settings)
        thread.start()
        if timeout:
            thread.join(timeout)

    def _write_settings(self) -> None:
        json_str = self.model_dump_json(indent=2, exclude_defaults=True)
        SETTINGS_FILE_NAME.write_text(json_str, errors="ignore")


Settings = SettingsV1


def reset_to_defaults() -> None:
    """Erase user settings and reset to defaults."""
    global _GLOBAL_SETTINGS
    if TESTING or os.getenv("MMGUI_NO_SETTINGS"):  # pragma: no cover
        return
    SETTINGS_FILE_NAME.unlink(missing_ok=True)
    _GLOBAL_SETTINGS = SettingsV1()
