"""Qlementine compatibility layer for PyQt6 and PySide6."""
# pyright: reportWildcardImportFromLibrary=false

from __future__ import annotations

from typing import TYPE_CHECKING

if not TYPE_CHECKING:
    try:
        from PyQt6Qlementine import *
    except ImportError:  # pragma: no cover
        try:
            from PySide6Qlementine import *
        except ImportError as e:
            raise ImportError(
                "Neither PyQt6Qlementine nor PySide6Qlementine is installed. "
            ) from e
