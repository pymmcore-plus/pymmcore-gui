from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_widgets import ConfigWizard
from pymmcore_widgets.hcwizard.finish_page import DEST_CONFIG

from micromanager_gui._util import (
    add_path_to_config_json,
    load_sys_config,
)

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from qtpy.QtWidgets import QWidget


class HardwareConfigWizard(ConfigWizard):
    """A wizard to create a new Micro-Manager hardware configuration file.

    Subclassing to load the newly created configuration file and to add it to the
    USER_CONFIGS_PATHS json file.
    """

    def __init__(
        self,
        config_file: str = "",
        core: CMMCorePlus | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(config_file, core, parent)

        self.setWindowTitle("Micro-Manager Hardware Configuration Wizard")

    def accept(self) -> None:
        """Accept the wizard and save the configuration to a file.

        Overriding to add the new configuration file to the USER_CONFIGS_PATHS json file
        and to load it.
        """
        super().accept()
        dest = self.field(DEST_CONFIG)
        # add the path to the USER_CONFIGS_PATHS list
        add_path_to_config_json(dest)
        load_sys_config(dest)
