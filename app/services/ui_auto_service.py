"""
Goal: Thin wrappers for UI automation tasks.
"""

from typing import List

from app.adapters.ui_auto import focus_window, list_windows


def windows() -> List[str]:
    return list_windows()


def focus(title_substring: str, strict: bool = False) -> bool:
    return focus_window(title_substring, strict)
