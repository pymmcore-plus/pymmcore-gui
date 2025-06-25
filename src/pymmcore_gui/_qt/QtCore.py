# pyright: reportWildcardImportFromLibrary=false

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from PyQt6 import QtCore
    from PyQt6.QtCore import *
    # from PySide6.QtCore import *

    Signal: TypeAlias = QtCore.pyqtSignal
else:
    try:
        from PyQt6.QtCore import *

        Signal = pyqtSignal

    except ImportError:  # pragma: no cover
        try:
            from PySide6.QtCore import *
        except ImportError as e:
            raise ImportError("Neither PyQt6 nor PySide6 is installed. ") from e
