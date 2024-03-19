from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_widgets import GroupPresetTableWidget

from micromanager_gui._util import load_sys_config_dialog, save_sys_config_dialog

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from qtpy.QtWidgets import QWidget


class _GroupsAndPresets(GroupPresetTableWidget):
    """Subclass of GroupPresetTableWidget.

    Overwrite the save and load methods to store the saved or loaded configuration in
    the USER_CONFIGS_PATHS json config file.
    """

    def __init__(
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent, mmcore=mmcore)

    def _save_cfg(self) -> None:
        """Open file dialog to save the current configuration."""
        save_sys_config_dialog(parent=self, mmcore=self._mmc)

    def _load_cfg(self) -> None:
        """Open file dialog to select a config file."""
        load_sys_config_dialog(parent=self, mmcore=self._mmc)
