"""
Goal: Use Word COM to compute word count. This is Windows-only.
"""
import os
from typing import Optional
try:
    import win32com.client as win32
except Exception as exc:
    win32 = None

def word_count(path: Optional[str]=None) -> int:
    """
    If a path is provided, open the document silently; otherwise use the active document if available.
    """
    if win32 is None:
        raise RuntimeError("win32com is not available. Install pywin32 and run on Windows.")
    word = win32.Dispatch("Word.Application")
    # don't flash any windows in the user's face
    word.Visible = False
    doc = None
    try:
        if path and os.path.exists(path):
            doc = word.Documents.Open(path, ReadOnly=True)
        else:
            if word.Documents.Count == 0:
                return 0
            doc = word.ActiveDocument
        # built-in statistic: 0 => wdStatisticWords
        count = doc.ComputeStatistics(0)
        return int(count)
    finally:
        if doc is not None:
            doc.Close(False)
        word.Quit()
