# pyright: reportOverlappingOverload=false, reportIncompatibleMethodOverride=false, reportAttributeAccessIssue=false
import typing

from pymmcore_gui._qt import QtCore, QtGui, QtWidgets

from . import (
    ActiveState,
    AlternateState,
    CheckState,
    ColorizeMode,
    ColorRole,
    FocusState,
    IconTheme,
    MouseState,
    RadiusesF,
    SelectionState,
    StatusBadge,
    StatusBadgeSize,
    Theme,
)

def activeStateToString(state: ActiveState) -> str: ...
def blurRadiusNecessarySpace(blurRadius: float) -> int: ...
def centerWidget(
    widget: QtWidgets.QWidget, host: QtWidgets.QWidget | None = ...
) -> None: ...
def checkStateToString(state: CheckState) -> str: ...
def clearFocus(widget: QtWidgets.QWidget, recursive: bool) -> None: ...
def clearLayout(layout: QtWidgets.QLayout) -> None: ...
def colorWithAlpha(
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    alpha: int,
) -> QtGui.QColor: ...
def colorWithAlphaF(
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    alpha: float,
) -> QtGui.QColor: ...
def colorizeImage(
    input: QtGui.QPixmap | QtGui.QImage,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> QtGui.QImage: ...
def colorizePixmap(
    input: QtGui.QPixmap | QtGui.QImage,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> QtGui.QPixmap: ...
def displayedShortcutString(
    shortcut: QtGui.QKeySequence
    | QtCore.QKeyCombination
    | QtGui.QKeySequence.StandardKey
    | str
    | int,
) -> str: ...
def drawArrowDown(rect: QtCore.QRect, p: QtGui.QPainter) -> None: ...
def drawArrowLeft(rect: QtCore.QRect, p: QtGui.QPainter) -> None: ...
def drawArrowRight(rect: QtCore.QRect, p: QtGui.QPainter) -> None: ...
def drawArrowUp(rect: QtCore.QRect, p: QtGui.QPainter) -> None: ...
def drawCalendarIndicator(
    rect: QtCore.QRect,
    p: QtGui.QPainter,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> None: ...
def drawCheckBoxIndicator(
    rect: QtCore.QRect, p: QtGui.QPainter, progress: float = ...
) -> None: ...
def drawCheckButton(
    p: QtGui.QPainter,
    rect: QtCore.QRect,
    radius: float,
    bgColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    borderColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    fgColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    borderWidth: float,
    progress: float,
    checkState: CheckState,
) -> None: ...
def drawCheckerboard(
    p: QtGui.QPainter,
    rect: QtCore.QRectF | QtCore.QRect,
    darkColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    lightColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    cellWidth: float,
) -> None: ...
def drawCloseIndicator(rect: QtCore.QRect, p: QtGui.QPainter) -> None: ...
def drawColorMark(
    p: QtGui.QPainter,
    rect: QtCore.QRect,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    borderColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    borderWidth: int = ...,
) -> None: ...
def drawColorMarkBorder(
    p: QtGui.QPainter,
    rect: QtCore.QRect,
    borderColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    borderWidth: int,
) -> None: ...
def drawComboBoxIndicator(rect: QtCore.QRect, p: QtGui.QPainter) -> None: ...
def drawDebugRect(rect: QtCore.QRect, p: QtGui.QPainter) -> None: ...
def drawDial(
    p: QtGui.QPainter,
    rect: QtCore.QRect,
    min: int,
    max: int,
    value: float,
    bgColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    handleColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    grooveColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    valueColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    markColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    grooveThickness: int,
    markLength: int,
    markThickness: int,
) -> None: ...
def drawDialTickMarks(
    p: QtGui.QPainter,
    tickmarksRect: QtCore.QRect,
    tickColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    min: int,
    max: int,
    tickThickness: int,
    tickLength: int,
    singleStep: int,
    pageStep: int,
    minArcLength: int,
) -> None: ...
def drawDoubleArrowRightIndicator(rect: QtCore.QRect, p: QtGui.QPainter) -> None: ...
def drawElidedMultiLineText(
    p: QtGui.QPainter,
    rect: QtCore.QRect,
    text: str,
    paintDevice: QtGui.QPaintDevice,
) -> None: ...
def drawEllipseBorder(
    p: QtGui.QPainter,
    rect: QtCore.QRectF | QtCore.QRect,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    borderWidth: float,
) -> None: ...
def drawGripIndicator(
    rect: QtCore.QRect,
    p: QtGui.QPainter,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    orientation: QtCore.Qt.Orientation,
) -> None: ...
def drawIcon(
    rect: QtCore.QRect,
    p: QtGui.QPainter,
    icon: QtGui.QIcon | QtGui.QPixmap,
    mouse: MouseState,
    checked: CheckState,
    widget: QtWidgets.QWidget,
    colorize: bool = ...,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int = ...,
) -> QtCore.QRect: ...
def drawMenuSeparator(
    p: QtGui.QPainter,
    rect: QtCore.QRect,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    thickness: int,
) -> None: ...
def drawPartiallyCheckedCheckBoxIndicator(
    rect: QtCore.QRect, p: QtGui.QPainter, progress: float = ...
) -> None: ...
def drawProgressBarValueRect(
    p: QtGui.QPainter,
    rect: QtCore.QRect,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    min: float,
    max: float,
    value: float,
    radius: float = ...,
    inverted: bool = ...,
) -> None: ...
def drawRadioButton(
    p: QtGui.QPainter,
    rect: QtCore.QRect,
    bgColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    borderColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    fgColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    borderWidth: float,
    progress: float,
) -> None: ...
def drawRadioButtonIndicator(
    rect: QtCore.QRect, p: QtGui.QPainter, progress: float = ...
) -> None: ...
@typing.overload
def drawRectBorder(
    p: QtGui.QPainter,
    rect: QtCore.QRect,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    borderWidth: float,
) -> None: ...
@typing.overload
def drawRectBorder(
    p: QtGui.QPainter,
    rect: QtCore.QRectF | QtCore.QRect,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    borderWidth: float,
) -> None: ...
@typing.overload
def drawRoundedRect(
    p: QtGui.QPainter,
    rect: QtCore.QRect,
    brush: QtGui.QBrush
    | QtCore.Qt.BrushStyle
    | QtCore.Qt.GlobalColor
    | QtGui.QColor
    | QtGui.QGradient
    | QtGui.QImage
    | QtGui.QPixmap,
    radiuses: RadiusesF,
) -> None: ...
@typing.overload
def drawRoundedRect(
    p: QtGui.QPainter,
    rect: QtCore.QRect,
    brush: QtGui.QBrush
    | QtCore.Qt.BrushStyle
    | QtCore.Qt.GlobalColor
    | QtGui.QColor
    | QtGui.QGradient
    | QtGui.QImage
    | QtGui.QPixmap,
    radius: float = ...,
) -> None: ...
@typing.overload
def drawRoundedRect(
    p: QtGui.QPainter,
    rect: QtCore.QRectF | QtCore.QRect,
    brush: QtGui.QBrush
    | QtCore.Qt.BrushStyle
    | QtCore.Qt.GlobalColor
    | QtGui.QColor
    | QtGui.QGradient
    | QtGui.QImage
    | QtGui.QPixmap,
    radiuses: RadiusesF,
) -> None: ...
@typing.overload
def drawRoundedRect(
    p: QtGui.QPainter,
    rect: QtCore.QRectF | QtCore.QRect,
    brush: QtGui.QBrush
    | QtCore.Qt.BrushStyle
    | QtCore.Qt.GlobalColor
    | QtGui.QColor
    | QtGui.QGradient
    | QtGui.QImage
    | QtGui.QPixmap,
    radius: float = ...,
) -> None: ...
@typing.overload
def drawRoundedRectBorder(
    p: QtGui.QPainter,
    rect: QtCore.QRect,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    borderWidth: float,
    radiuses: RadiusesF,
) -> None: ...
@typing.overload
def drawRoundedRectBorder(
    p: QtGui.QPainter,
    rect: QtCore.QRect,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    borderWidth: float,
    radius: float = ...,
) -> None: ...
@typing.overload
def drawRoundedRectBorder(
    p: QtGui.QPainter,
    rect: QtCore.QRectF | QtCore.QRect,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    borderWidth: float,
    radiuses: RadiusesF,
) -> None: ...
@typing.overload
def drawRoundedRectBorder(
    p: QtGui.QPainter,
    rect: QtCore.QRectF | QtCore.QRect,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    borderWidth: float,
    radius: float = ...,
) -> None: ...
def drawRoundedTriangle(
    p: QtGui.QPainter,
    rect: QtCore.QRectF | QtCore.QRect,
    radius: float = ...,
) -> None: ...
def drawShortcut(
    p: QtGui.QPainter,
    shortcut: QtGui.QKeySequence
    | QtCore.QKeyCombination
    | QtGui.QKeySequence.StandardKey
    | str
    | int,
    rect: QtCore.QRect,
    theme: Theme,
    enabled: bool,
    alignment: QtCore.Qt.AlignmentFlag = ...,
) -> None: ...
def drawSliderTickMarks(
    p: QtGui.QPainter,
    tickmarksRect: QtCore.QRect,
    tickColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    min: int,
    max: int,
    interval: int,
    tickThickness: int,
    singleStep: int,
    pageStep: int,
) -> None: ...
def drawSpinBoxArrowIndicator(
    rect: QtCore.QRect,
    p: QtGui.QPainter,
    buttonSymbol: QtWidgets.QAbstractSpinBox.ButtonSymbols,
    subControl: QtWidgets.QStyle.SubControl,
    iconSize: QtCore.QSize,
) -> None: ...
def drawStatusBadge(
    p: QtGui.QPainter,
    rect: QtCore.QRect,
    statusBadge: StatusBadge,
    size: StatusBadgeSize,
    theme: Theme,
) -> None: ...
def drawSubMenuIndicator(rect: QtCore.QRect, p: QtGui.QPainter) -> None: ...
def drawTab(
    p: QtGui.QPainter,
    rect: QtCore.QRect,
    radiuses: RadiusesF,
    bgColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    drawShadow: bool = ...,
    shadowColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int = ...,
) -> None: ...
def drawTabShadow(
    p: QtGui.QPainter,
    rect: QtCore.QRect,
    radius: RadiusesF,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> None: ...
def drawToolBarExtensionIndicator(rect: QtCore.QRect, p: QtGui.QPainter) -> None: ...
def drawTreeViewIndicator(
    rect: QtCore.QRect, p: QtGui.QPainter, open: bool
) -> None: ...
def focusStateToString(state: FocusState) -> str: ...
def getActiveState(state: QtWidgets.QStyle.StateFlag) -> ActiveState: ...
def getAlternateState(
    state: QtWidgets.QStyleOptionViewItem.ViewItemFeature,
) -> AlternateState: ...
def getBlurredPixmap(
    input: QtGui.QPixmap | QtGui.QImage, blurRadius: float
) -> QtGui.QPixmap: ...
def getCachedPixmap(
    input: QtGui.QPixmap | QtGui.QImage,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    mode: ColorizeMode,
) -> QtGui.QPixmap: ...
@typing.overload
def getCheckState(state: QtWidgets.QStyle.StateFlag) -> CheckState: ...
@typing.overload
def getCheckState(state: QtCore.Qt.CheckState) -> CheckState: ...
@typing.overload
def getCheckState(checked: bool) -> CheckState: ...
@typing.overload
def getColorRole(checked: CheckState) -> ColorRole: ...
@typing.overload
def getColorRole(state: QtWidgets.QStyle.StateFlag, isDefault: bool) -> ColorRole: ...
@typing.overload
def getColorRole(checked: bool, isDefault: bool) -> ColorRole: ...
def getColorSourceOver(
    bg: QtGui.QColor | str | QtGui.QRgba64 | typing.Any | QtCore.Qt.GlobalColor | int,
    fg: QtGui.QColor | str | QtGui.QRgba64 | typing.Any | QtCore.Qt.GlobalColor | int,
) -> QtGui.QColor: ...
def getColorizedPixmap(
    input: QtGui.QPixmap | QtGui.QImage,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> QtGui.QPixmap: ...
def getComboBoxItemMouseState(
    state: QtWidgets.QStyle.StateFlag,
) -> MouseState: ...
def getContrastRatio(
    c1: QtGui.QColor | str | QtGui.QRgba64 | typing.Any | QtCore.Qt.GlobalColor | int,
    c2: QtGui.QColor | str | QtGui.QRgba64 | typing.Any | QtCore.Qt.GlobalColor | int,
) -> float: ...
def getDpi(widget: QtWidgets.QWidget) -> float: ...
@typing.overload
def getDropShadowPixmap(
    size: QtCore.QSize,
    borderRadius: float,
    blurRadius: float,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int = ...,
) -> QtGui.QPixmap: ...
@typing.overload
def getDropShadowPixmap(
    input: QtGui.QPixmap | QtGui.QImage,
    blurRadius: float,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int = ...,
) -> QtGui.QPixmap: ...
@typing.overload
def getExtendedImage(input: QtGui.QImage, padding: int) -> QtGui.QImage: ...
@typing.overload
def getExtendedImage(
    input: QtGui.QPixmap | QtGui.QImage, padding: int
) -> QtGui.QImage: ...
@typing.overload
def getFocusState(state: QtWidgets.QStyle.StateFlag) -> FocusState: ...
@typing.overload
def getFocusState(focused: bool) -> FocusState: ...
def getIconMode(mouse: MouseState) -> QtGui.QIcon.Mode: ...
def getIconState(checked: CheckState) -> QtGui.QIcon.State: ...
def getImageAspectRatio(path: str) -> float: ...
def getLayoutHSpacing(widget: QtWidgets.QWidget) -> int: ...
def getLayoutMargins(widget: QtWidgets.QWidget) -> QtCore.QMargins: ...
def getLayoutVSpacing(widget: QtWidgets.QWidget) -> int: ...
def getMenuIndicatorPath(rect: QtCore.QRect) -> QtGui.QPainterPath: ...
def getMenuItemMouseState(state: QtWidgets.QStyle.StateFlag) -> MouseState: ...
@typing.overload
def getMouseState(state: QtWidgets.QStyle.StateFlag) -> MouseState: ...
@typing.overload
def getMouseState(pressed: bool, hovered: bool, enabled: bool) -> MouseState: ...
def getMultipleRadiusesRectPath(
    rect: QtCore.QRectF | QtCore.QRect, radiuses: RadiusesF
) -> QtGui.QPainterPath: ...
@typing.overload
def getPaletteColorGroup(mouse: MouseState) -> QtGui.QPalette.ColorGroup: ...
@typing.overload
def getPaletteColorGroup(
    state: QtWidgets.QStyle.StateFlag,
) -> QtGui.QPalette.ColorGroup: ...
def getPixelRatio(w: QtWidgets.QWidget) -> float: ...
def getPixmap(
    icon: QtGui.QIcon | QtGui.QPixmap,
    iconSize: QtCore.QSize,
    mouse: MouseState,
    checked: CheckState,
    widget: QtWidgets.QWidget,
) -> QtGui.QPixmap: ...
def getScrollBarHandleState(
    state: QtWidgets.QStyle.StateFlag,
    activeSubControls: QtWidgets.QStyle.SubControl,
) -> MouseState: ...
def getSelectionState(state: QtWidgets.QStyle.StateFlag) -> SelectionState: ...
def getSliderHandleState(
    state: QtWidgets.QStyle.StateFlag,
    activeSubControls: QtWidgets.QStyle.SubControl,
) -> MouseState: ...
def getState(
    enabled: bool, hover: bool, pressed: bool
) -> QtWidgets.QStyle.StateFlag: ...
def getTabCount(parentWidget: QtWidgets.QWidget) -> int: ...
def getTabIndex(
    optTab: QtWidgets.QStyleOptionTab, parentWidget: QtWidgets.QWidget
) -> int: ...
def getTabItemMouseState(
    state: QtWidgets.QStyle.StateFlag, tabIsHovered: bool
) -> MouseState: ...
def getTabPath(rect: QtCore.QRect, radiuses: RadiusesF) -> QtGui.QPainterPath: ...
def getTickInterval(
    tickInterval: int,
    singleStep: int,
    pageStep: int,
    min: int,
    max: int,
    sliderLength: int,
) -> int: ...
def getTintedPixmap(
    input: QtGui.QPixmap | QtGui.QImage,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> QtGui.QPixmap: ...
def getToolButtonMouseState(
    state: QtWidgets.QStyle.StateFlag,
) -> MouseState: ...
def getTopLevelMenu(menu: QtWidgets.QMenu) -> QtWidgets.QMenu: ...
def getWindow(widget: QtWidgets.QWidget) -> QtGui.QWindow: ...
def isPointInRoundedRect(
    point: QtCore.QPointF | QtCore.QPoint | QtGui.QPainterPath.Element,
    rect: QtCore.QRectF | QtCore.QRect,
    cornerRadius: float,
) -> bool: ...
def makeArrowLeftPixmap(
    size: QtCore.QSize,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> QtGui.QPixmap: ...
def makeArrowRightPixmap(
    size: QtCore.QSize,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> QtGui.QPixmap: ...
def makeCalendarPixmap(
    size: QtCore.QSize,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> QtGui.QPixmap: ...
def makeCheckPixmap(
    size: QtCore.QSize,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> QtGui.QPixmap: ...
def makeClearButtonPixmap(
    size: QtCore.QSize,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> QtGui.QPixmap: ...
def makeDoubleArrowRightPixmap(
    size: QtCore.QSize,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> QtGui.QPixmap: ...
def makeFitPixmap(
    input: QtGui.QPixmap | QtGui.QImage, size: QtCore.QSize
) -> QtGui.QPixmap: ...
def makeHorizontalLine(
    parentWidget: QtWidgets.QWidget, maxWidth: int = ...
) -> QtWidgets.QWidget: ...
@typing.overload
def makeIconFromSvg(
    svgPath: str, iconTheme: IconTheme, size: QtCore.QSize = ...
) -> QtGui.QIcon: ...
@typing.overload
def makeIconFromSvg(svgPath: str, size: QtCore.QSize) -> QtGui.QIcon: ...
def makeMessageBoxCriticalPixmap(
    size: QtCore.QSize,
    bgColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    fgColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> QtGui.QPixmap: ...
def makeMessageBoxInformationPixmap(
    size: QtCore.QSize,
    bgColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    fgColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> QtGui.QPixmap: ...
def makeMessageBoxQuestionPixmap(
    size: QtCore.QSize,
    bgColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    fgColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> QtGui.QPixmap: ...
def makeMessageBoxWarningPixmap(
    size: QtCore.QSize,
    bgColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    fgColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> QtGui.QPixmap: ...
@typing.overload
def makePixmapFromSvg(svgPath: str, size: QtCore.QSize) -> QtGui.QPixmap: ...
@typing.overload
def makePixmapFromSvg(
    backgroundSvgPath: str,
    backgroundSvgColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    foregroundSvgPath: str,
    foregroundSvgColor: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
    size: QtCore.QSize,
) -> QtGui.QPixmap: ...
@typing.overload
def makeRoundedPixmap(
    input: QtGui.QPixmap | QtGui.QImage, radiuses: RadiusesF
) -> QtGui.QPixmap: ...
@typing.overload
def makeRoundedPixmap(
    input: QtGui.QPixmap | QtGui.QImage, radius: float
) -> QtGui.QPixmap: ...
@typing.overload
def makeRoundedPixmap(
    input: QtGui.QPixmap | QtGui.QImage,
    topLeft: float,
    topRight: float,
    bottomRight: float,
    bottomLeft: float,
) -> QtGui.QPixmap: ...
def makeToolBarExtensionPixmap(
    size: QtCore.QSize,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> QtGui.QPixmap: ...
def makeVerticalLine(
    parentWidget: QtWidgets.QWidget, maxHeight: int = ...
) -> QtWidgets.QWidget: ...
def mouseStateToString(state: MouseState) -> str: ...
def pixelSizeToPointSize(pixelSize: float, dpi: float) -> float: ...
def pointSizeToPixelSize(pointSize: float, dpi: float) -> float: ...
def printState(state: QtWidgets.QStyle.StateFlag) -> str: ...
def removeTrailingWhitespaces(str: str) -> str: ...
def selectionStateToString(state: SelectionState) -> str: ...
def shortcutSizeHint(
    shortcut: QtGui.QKeySequence
    | QtCore.QKeyCombination
    | QtGui.QKeySequence.StandardKey
    | str
    | int,
    theme: Theme,
) -> QtCore.QSize: ...
def shouldHaveBoldFont(w: QtWidgets.QWidget) -> bool: ...
def shouldHaveExternalFocusFrame(w: QtWidgets.QWidget) -> bool: ...
def shouldHaveHoverEvents(w: QtWidgets.QWidget) -> bool: ...
def shouldHaveMouseTracking(w: QtWidgets.QWidget) -> bool: ...
def shouldHaveTabFocus(w: QtWidgets.QWidget) -> bool: ...
def shouldNotBeVerticallyCompressed(w: QtWidgets.QWidget) -> bool: ...
def shouldNotHaveWheelEvents(w: QtWidgets.QWidget) -> bool: ...
def textWidth(fm: QtGui.QFontMetrics, text: str) -> int: ...
def tintPixmap(
    input: QtGui.QPixmap | QtGui.QImage,
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> QtGui.QPixmap: ...
def toHexRGB(
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> str: ...
def toHexRGBA(
    color: QtGui.QColor
    | str
    | QtGui.QRgba64
    | typing.Any
    | QtCore.Qt.GlobalColor
    | int,
) -> str: ...
