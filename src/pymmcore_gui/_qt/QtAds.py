# pyright: reportWildcardImportFromLibrary=false

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from PyQt6Ads import *
    # from PySide6QtAds import *
else:
    try:
        from PyQt6Ads import *
    except ImportError:  # pragma: no cover
        try:
            from PySide6QtAds import *
            from PySide6QtAds.PySide6QtAds import ads

            globals().update(vars(ads))
        except ImportError as e:
            raise ImportError(
                f"Neither PyQt6Ads nor PySide6Ads is installed. {e}"
            ) from e
