from pymmcore_widgets import PixelConfigurationWidget

from pymmcore_gui._qt.QtAds import CDockWidget


class _PixelConfigurationWidget(PixelConfigurationWidget):
    def close(self) -> bool:
        # Hide the parent CDockWidget container instead of closing this widget,
        # so the widget is preserved and can be reopened.
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, CDockWidget):
                parent.toggleView(False)
                return True
            parent = parent.parent()
        return super().close()
