# pyright: reportWildcardImportFromLibrary=false

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtOpenGLWidgets import *
else:
    try:
        from PyQt6.QtOpenGLWidgets import *
    except ImportError:  # pragma: no cover
        try:
            from PySide6.QtOpenGLWidgets import *
        except ImportError as e:
            raise ImportError("Neither PyQt6 nor PySide6 is installed. ") from e
