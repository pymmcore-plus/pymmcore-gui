"""QtAds-aware style extending QlementineStyle.

QtAds applies a global stylesheet to CDockManager, which creates a QStyleSheetStyle
proxy that intercepts painting for all descendant widgets — breaking custom QStyle
implementations like QlementineStyle. This module subclasses QlementineStyle directly
and renders QtAds dock tabs and title bars through the QStyle system, using
Qlementine's theme tokens for full theme awareness.

Usage::

    app.setStyle(AdsAwareQlementineStyle())
    dock_manager.setStyleSheet("")  # remove QtAds default CSS
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyconify import svg_path

from pymmcore_gui._qt.Qlementine import (  # type: ignore[attr-defined]
    AutoIconColor,
    MouseState,
    QlementineStyle,
    SelectionState,
    Theme,
)
from pymmcore_gui._qt.QtCore import QJsonDocument, QRectF, Qt
from pymmcore_gui._qt.QtGui import QColor, QPainter, QPalette, QPen
from pymmcore_gui._qt.QtWidgets import (
    QScrollArea,
    QStyle,
    QStyleOption,
    QStyleOptionToolButton,
    QWidget,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

# QtAds widget objectNames
ADS_TAB_CLOSE = "tabCloseButton"
ADS_TAB_LABEL = "dockWidgetTabLabel"
ADS_TABS_MENU = "tabsMenuButton"
ADS_TABS_CONTAINER = "tabsContainerWidget"
ADS_TITLE_BAR = "dockAreaTitleBar"
ADS_AREA_CLOSE = "dockAreaCloseButton"
ADS_AUTO_HIDE = "dockAreaAutoHideButton"
ADS_DETACH = "detachGroupButton"

# QtAds dynamic property names
ADS_ACTIVE_TAB = "activeTab"

# Icon keys for QtAds buttons, resolved via pyconify at runtime.
_ADS_ICON_MAP = {
    ADS_TAB_CLOSE: "codicon:close",
    ADS_TABS_MENU: "codicon:chevron-down",
    ADS_DETACH: "tabler:queue-pop-out",
    ADS_AREA_CLOSE: "codicon:close",
    ADS_AUTO_HIDE: "codicon:pinned",
}


def _mouse_state(option: QStyleOption) -> MouseState:
    """Map QStyle state flags to Qlementine MouseState."""
    state = option.state
    if not (state & QStyle.StateFlag.State_Enabled):
        return MouseState.Disabled
    if state & QStyle.StateFlag.State_Sunken:
        return MouseState.Pressed
    if state & QStyle.StateFlag.State_MouseOver:
        return MouseState.Hovered
    return MouseState.Normal


class AdsAwareQlementineStyle(QlementineStyle):
    """QlementineStyle subclass with QtAds dock widget awareness."""

    def __init__(self) -> None:
        super().__init__()
        self.setAutoIconColor(AutoIconColor.ForegroundColor)

    # ---- Drawing overrides ----

    def drawControl(
        self,
        element: QStyle.ControlElement,
        option: QStyleOption | None,
        painter: QPainter | None,
        w: QWidget | None = None,
    ) -> None:
        if element == QStyle.ControlElement.CE_ShapedFrame and w and option and painter:
            active = w.property(ADS_ACTIVE_TAB)
            if active is not None:
                self._draw_dock_tab(option, painter, w, bool(active))
                return
            if w.objectName() == ADS_TITLE_BAR:
                self._draw_title_bar(option, painter, w)
                return
        super().drawControl(element, option, painter, w)

    def drawComplexControl(
        self,
        control: QStyle.ComplexControl,
        option: QStyleOption | None,
        painter: QPainter | None,
        w: QWidget | None = None,
    ) -> None:
        # Suppress the double-chevron menu indicator on the tabs menu
        if (
            control == QStyle.ComplexControl.CC_ToolButton
            and w is not None
            and w.objectName() == ADS_TABS_MENU
            and isinstance(option, QStyleOptionToolButton)
        ):
            option.features &= ~QStyleOptionToolButton.ToolButtonFeature.HasMenu
        super().drawComplexControl(control, option, painter, w)

    # ---- Widget polishing ----

    def polish(self, obj: Any) -> Any:
        result = super().polish(obj)
        if not isinstance(obj, QWidget):
            return result

        name = obj.objectName()

        # Set themed icons on QtAds buttons.
        # AutoIconColor (set in __init__) ensures Qlementine
        # re-colorizes them at paint time with the correct fg color.
        if name in _ADS_ICON_MAP and hasattr(obj, "setIcon"):
            obj.setIcon(self.makeThemedIcon(str(svg_path(_ADS_ICON_MAP[name]))))

        # Flat close buttons so Qlementine skips the button bevel
        if name == ADS_TAB_CLOSE and hasattr(obj, "setFlat"):
            obj.setFlat(True)

        # Set title bar background on intermediate widgets that would
        # otherwise auto-fill with palette(Window), covering the
        # darker title bar painted by _draw_title_bar.
        tb_bg = self.tabBarBackgroundColor(MouseState.Normal)
        if obj.property(ADS_ACTIVE_TAB) is not None or name == ADS_TABS_CONTAINER:
            _set_widget_bg(obj, tb_bg)
        elif name == ADS_TITLE_BAR:
            for child in obj.findChildren(QScrollArea):
                _set_widget_bg(child, tb_bg)
                _set_widget_bg(child.viewport(), tb_bg)

        return result

    # ---- Private drawing helpers ----

    def _draw_dock_tab(
        self,
        option: QStyleOption,
        painter: QPainter,
        widget: QWidget,
        is_active: bool,
    ) -> None:
        mouse = _mouse_state(option)
        sel = SelectionState.Selected if is_active else SelectionState.NotSelected
        bg = self.tabBackgroundColor(mouse, sel)

        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        if is_active:
            painter.fillRect(option.rect, bg)
        else:
            if bg.alpha() > 0:
                painter.setBrush(bg)
                painter.drawRoundedRect(QRectF(option.rect), 6.0, 6.0)
            # Separator between inactive tabs
            sep = QColor(widget.palette().color(QPalette.ColorRole.WindowText))
            sep.setAlphaF(0.2)
            painter.setPen(QPen(sep, 1))
            x = int(option.rect.right())
            painter.drawLine(
                x,
                option.rect.top() + 5,
                x,
                option.rect.bottom() - 5,
            )

        painter.restore()
        self._update_tab_label_color(widget, mouse, sel)

    def _update_tab_label_color(
        self, tab: QWidget, mouse: MouseState, sel: SelectionState
    ) -> None:
        target = self.tabForegroundColor(mouse, sel)
        for child in tab.children():
            if (
                isinstance(child, QWidget)
                and child.objectName() == ADS_TAB_LABEL
                and child.palette().color(QPalette.ColorRole.WindowText) != target
            ):
                pal = child.palette()
                pal.setColor(QPalette.ColorRole.WindowText, target)
                child.setPalette(pal)

    def _draw_title_bar(
        self, option: QStyleOption, painter: QPainter, widget: QWidget
    ) -> None:
        painter.save()
        painter.fillRect(option.rect, self.tabBarBackgroundColor(MouseState.Normal))
        painter.setPen(QPen(self.tabBarBottomShadowColor(), 1))
        painter.drawLine(
            option.rect.left(),
            option.rect.bottom(),
            option.rect.right(),
            option.rect.bottom(),
        )
        painter.restore()


def _set_widget_bg(widget: QWidget, color: QColor) -> None:
    pal = widget.palette()
    pal.setColor(QPalette.ColorRole.Window, color)
    widget.setPalette(pal)
    widget.setAutoFillBackground(True)


radix_slate_blue = {
    "meta": {
        "name": "Radix Slate Blue",
        "version": "1.0.0",
        "author": "WorkOS/Radix (adapted)",
    },
    "background_color_main1": "#111113",
    "background_color_main2": "#18191B",
    "background_color_main3": "#212225",
    "background_color_main4": "#272A2D",
    "background_color_workspace": "#0C0C0E",
    "background_color_tab_bar": "#111113",
    "neutral_color": "#2E3135",
    "neutral_color_hovered": "#363A3F",
    "neutral_color_pressed": "#3E4349",
    "neutral_color_disabled": "#1C1D1F",
    "focus_color": "#0090FF6A",
    "primary_color": "#0090FF",
    "primary_color_hovered": "#3B9EFF",
    "primary_color_pressed": "#6CB4FF",
    "primary_color_disabled": "#142840",
    "primary_color_foreground": "#FFFFFF",
    "primary_color_foreground_hovered": "#FFFFFF",
    "primary_color_foreground_pressed": "#FFFFFF",
    "primary_color_foreground_disabled": "#384858",
    "primary_alternative_color": "#3E63DD",
    "primary_alternative_color_hovered": "#5472E4",
    "primary_alternative_color_pressed": "#6A81EB",
    "primary_alternative_color_disabled": "#161E38",
    "secondary_color": "#EDEEF0",
    "secondary_color_hovered": "#D0D2D6",
    "secondary_color_pressed": "#DFE0E3",
    "secondary_color_disabled": "#EDEEF033",
    "secondary_color_foreground": "#18191B",
    "secondary_color_foreground_hovered": "#18191B",
    "secondary_color_foreground_pressed": "#18191B",
    "secondary_color_foreground_disabled": "#18191B3F",
    "secondary_alternative_color": "#696E77",
    "secondary_alternative_color_hovered": "#868B94",
    "secondary_alternative_color_pressed": "#9DA2AA",
    "secondary_alternative_color_disabled": "#696E773F",
    "status_color_success": "#30A46C",
    "status_color_success_hovered": "#3DB57D",
    "status_color_success_pressed": "#4AC68E",
    "status_color_success_disabled": "#14221C",
    "status_color_info": "#0090FF",
    "status_color_info_hovered": "#3B9EFF",
    "status_color_info_pressed": "#6CB4FF",
    "status_color_info_disabled": "#101E30",
    "status_color_warning": "#F5D90A",
    "status_color_warning_hovered": "#F6DE2E",
    "status_color_warning_pressed": "#F7E352",
    "status_color_warning_disabled": "#2A2810",
    "status_color_error": "#E5484D",
    "status_color_error_hovered": "#EC5D62",
    "status_color_error_pressed": "#F37277",
    "status_color_error_disabled": "#2C1416",
    "status_color_foreground": "#FFFFFF",
    "status_color_foreground_hovered": "#FFFFFF",
    "status_color_foreground_pressed": "#FFFFFF",
    "status_color_foreground_disabled": "#FFFFFF26",
    "shadow_color1": "#00000066",
    "shadow_color2": "#000000BB",
    "shadow_color3": "#000000FF",
    "border_color": "#43484E",
    "border_color_hovered": "#50565E",
    "border_color_pressed": "#5D646E",
    "border_color_disabled": "#282A2E",
    "semi_transparent_color1": "#0090FF0A",
    "semi_transparent_color2": "#0090FF14",
    "semi_transparent_color3": "#0090FF1E",
    "semi_transparent_color4": "#0090FF28",
    "use_system_fonts": True,
    "font_size": 13,
    "font_size_monospace": 13,
    "font_size_h1": 34,
    "font_size_h2": 26,
    "font_size_h3": 22,
    "font_size_h4": 18,
    "font_size_h5": 14,
    "font_size_s1": 10,
    "animation_duration": 200,
    "focus_animation_duration": 400,
    "slider_animation_duration": 120,
    "border_radius": 8.0,
    "check_box_border_radius": 4.0,
    "menu_item_border_radius": 6.0,
    "menu_bar_item_border_radius": 4.0,
    "border_width": 1,
    "control_height_large": 28,
    "control_height_medium": 24,
    "control_height_small": 18,
    "control_default_width": 120,
    "dial_mark_length": 8,
    "dial_mark_thickness": 2,
    "dial_tick_length": 4,
    "dial_tick_spacing": 4,
    "dial_groove_thickness": 4,
    "focus_border_width": 2,
    "icon_extent": 16,
    "slider_tick_size": 3,
    "slider_tick_spacing": 2,
    "slider_tick_thickness": 1,
    "slider_groove_height": 4,
    "progress_bar_groove_height": 6,
    "spacing": 8,
    "scroll_bar_thickness_full": 12,
    "scroll_bar_thickness_small": 6,
    "scroll_bar_margin": 0,
    "tab_bar_padding_top": 4,
    "tab_bar_tab_max_width": 0,
    "tab_bar_tab_min_width": 0,
}


def _to_camel_case_dict(d: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively convert all dict keys from snake_case to camelCase."""
    out: dict[str, Any] = {}
    for key, value in d.items():
        part0, *rest = key.split("_")
        camel_key = part0 + "".join(p.capitalize() for p in rest)
        if isinstance(value, dict):
            value = _to_camel_case_dict(value)
        out[camel_key] = value
    return out


def make_qlementine_theme(theme: dict | None = None, /, **kwargs: Any) -> Theme:
    """Convert a ThemeDict or Theme configuration into a Qlementine.Theme instance."""
    camel_dict = _to_camel_case_dict({**(theme or {}), **kwargs})
    json_doc = QJsonDocument.fromVariant(camel_dict)
    return Theme.fromJsonDoc(json_doc)


def apply_dark_theme(style: QlementineStyle) -> None:
    """Apply a dark Qlementine theme to the given style."""
    style.setTheme(make_qlementine_theme(radix_slate_blue))
