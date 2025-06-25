"""Compatibility layer for PyQt6 and PySide6.

We use this to ensure that our code can run with either PyQt6 or PySide6
without modification (in case we need to switch to PySide6 in the future for licensing
reasons).

We use this instead of qtpy because:
- we want better control of type hints (for stricter Qt-side type checking)
- we need to also map PyQt6Ads and PySide6QtAds
- it's not that much code ... and not hard to maintain
"""
