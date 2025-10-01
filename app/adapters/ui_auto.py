"""
Goal: Small UI automation helpers: list windows and focus a window by title substring.
"""
from typing import List
import pywinauto

def list_windows() -> List[str]:
    titles = []
    for w in pywinauto.findwindows.find_elements():
        t = w.name or ""
        if t.strip():
            titles.append(t.strip())
    return sorted(set(titles))

def focus_window(substr: str, strict: bool=False) -> bool:
    # Try to find a window whose title matches (contains or equals based on strict)
    for w in pywinauto.findwindows.find_elements():
        t = (w.name or "").strip()
        if not t: 
            continue
        if (strict and t == substr) or ((not strict) and substr.lower() in t.lower()):
            try:
                app = pywinauto.Application().connect(handle=w.handle)
                app.top_window().set_focus()
                return True
            except Exception:
                continue
    return False
