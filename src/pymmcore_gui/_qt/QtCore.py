# pyright: reportWildcardImportFromLibrary=false

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from PySide6.QtCore import *
else:
    try:
        from PyQt6.QtCore import *

        Signal = pyqtSignal
        Property = pyqtProperty
        SignalInstance = pyqtBoundSignal

    except ImportError:  # pragma: no cover
        try:
            from PySide6.QtCore import *
        except ImportError as e:
            raise ImportError("Neither PyQt6 nor PySide6 is installed. ") from e
