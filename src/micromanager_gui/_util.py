from __future__ import annotations

from pathlib import Path
from typing import ContextManager, cast
from warnings import warn

from platformdirs import user_config_dir
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.core.events import CMMCoreSignaler, PCoreSignaler
from qtpy.QtWidgets import (
    QFileDialog,
    QWidget,
)
from superqt.utils import signals_blocked

PLATE_FROM_CALIBRATION = "custom_from_calibration"
USER_DIR = Path(user_config_dir("napari_micromanager"))
USER_CONFIGS_PATHS = USER_DIR / "system_configurations.json"


def block_core(mmcore_events: CMMCoreSignaler | PCoreSignaler) -> ContextManager:
    """Block core signals."""
    if isinstance(mmcore_events, CMMCoreSignaler):
        return mmcore_events.blocked()  # type: ignore
    elif isinstance(mmcore_events, PCoreSignaler):
        return signals_blocked(mmcore_events)  # type: ignore
    else:
        raise ValueError("Unknown core signaler.")


def add_path_to_config_json(path: Path | str) -> None:
    """Update the stystem configurations json file with the new path."""
    import json

    if not USER_CONFIGS_PATHS.exists():
        return

    if isinstance(path, Path):
        path = str(path)

    # Read the existing data
    try:
        with open(USER_CONFIGS_PATHS) as f:
            data = json.load(f)
    except json.JSONDecodeError:
        data = {"paths": []}

    # Append the new path. using insert so we leave the empty string at the end
    paths = cast(list, data.get("paths", []))
    if path in paths:
        paths.remove(path)
    paths.insert(0, path)

    # Write the data back to the file
    with open(USER_CONFIGS_PATHS, "w") as f:
        json.dump({"paths": paths}, f)


def save_sys_config_dialog(
    parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
) -> None:
    """Open file dialog to save a config file.

    The file will be also saved in the USER_CONFIGS_PATHS jason file if it doesn't
    yet exist.
    """
    (filename, _) = QFileDialog.getSaveFileName(
        parent, "Save Micro-Manager Configuration."
    )
    if filename:
        filename = filename if str(filename).endswith(".cfg") else f"{filename}.cfg"
        mmcore = mmcore or CMMCorePlus.instance()
        mmcore.saveSystemConfiguration(filename)
        add_path_to_config_json(filename)


def load_sys_config_dialog(
    parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
) -> None:
    """Open file dialog to select a config file.

    The loaded file will be also saved in the USER_CONFIGS_PATHS jason file if it
    doesn't yet exist.
    """
    (filename, _) = QFileDialog.getOpenFileName(
        parent, "Select a Micro-Manager configuration file", "", "cfg(*.cfg)"
    )
    if filename:
        add_path_to_config_json(filename)
        mmcore = mmcore or CMMCorePlus.instance()
        mmcore.loadSystemConfiguration(filename)


def load_sys_config(config: Path | str, mmcore: CMMCorePlus | None = None) -> None:
    """Load a system configuration with a warning if the file is not found."""
    mmcore = mmcore or CMMCorePlus.instance()
    try:
        mmcore.loadSystemConfiguration(config)
    except FileNotFoundError:
        # don't crash if the user passed an invalid config
        warn(f"Config file {config} not found. Nothing loaded.", stacklevel=2)
