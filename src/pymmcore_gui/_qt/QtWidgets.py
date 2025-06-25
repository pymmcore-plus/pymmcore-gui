# pyright: reportWildcardImportFromLibrary=false

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from PyQt6.QtWidgets import *
    # from PySide6.QtWidgets import *
else:
    try:
        from PyQt6.QtWidgets import *
    except ImportError:  # pragma: no cover
        try:
            from PySide6.QtWidgets import *
        except ImportError as e:
            raise ImportError("Neither PyQt6 nor PySide6 is installed. ") from e
