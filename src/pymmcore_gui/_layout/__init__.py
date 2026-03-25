"""VS Code-style workbench layout components."""

from ._activity_bar import ActivityBar
from ._enums import ActivityBarPosition, PanelAlignment, ViewContainerLocation
from ._pane_container import PaneContainer, SidebarContainer
from ._splitter_utils import splitter_size
from ._workbench import WorkbenchWidget

__all__ = [
    "ActivityBar",
    "ActivityBarPosition",
    "PaneContainer",
    "PanelAlignment",
    "SidebarContainer",
    "ViewContainerLocation",
    "WorkbenchWidget",
    "splitter_size",
]
