from __future__ import annotations

from enum import Enum


class PanelAlignment(Enum):
    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"
    JUSTIFY = "justify"


class ActivityBarPosition(Enum):
    DEFAULT = "default"
    TOP = "top"
    BOTTOM = "bottom"
    HIDDEN = "hidden"


class ViewContainerLocation(Enum):
    LEFT_SIDEBAR = "left_sidebar"
    RIGHT_SIDEBAR = "right_sidebar"
    PANEL = "panel"
