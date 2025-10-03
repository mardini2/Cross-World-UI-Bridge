"""
Goal
- Offer minimal but useful Word automation without bloating the Agent:
  - open_document(path: str | None) -> bool
  - type_text(text: str) -> int
  - save() -> str
  - quit() -> bool
  - keep your existing count_words(path) wrapper (via adapter) for quick metrics.

Notes
- Uses pywin32 (win32com) if available. Returns friendly errors from the Agent if not installed.
- Maintains a single visible Word instance; lazily created on first call.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional, cast

# Adapter function for your previous simple API
try:
    from app.adapters.word_com import word_count as _word_count  # runtime import
except Exception:
    _word_count = None  # type: ignore[assignment]

# Import COM at runtime with broad typing to avoid mypy issues when pywin32 is absent
try:
    import win32com.client as _win32
except Exception:
    _win32 = None  # type: ignore[assignment]

# Singleton instance storage with broad runtime typing
_APP: dict[str, Any] = {"word": None, "doc": None}


def _ensure_word() -> Any:
    """Create (or return) a visible Word instance."""
    if _win32 is None:
        raise RuntimeError("pywin32_not_installed")
    if _APP["word"] is None:
        word = _win32.Dispatch("Word.Application")  # late-bound COM object
        word.Visible = True
        _APP["word"] = word
    return _APP["word"]


def open_document(path: Optional[str] = None) -> bool:
    """Open an existing .docx or create a new one."""
    word = _ensure_word()
    if path:
        doc = word.Documents.Open(str(Path(path).resolve()))
    else:
        doc = word.Documents.Add()
    _APP["doc"] = doc
    return True


def type_text(text: str) -> int:
    """Type plain text at the current cursor position."""
    word = _ensure_word()
    if _APP.get("doc") is None:
        open_document(None)
    sel = cast(Any, word.Selection)  # late-bound COM
    sel.TypeText(text)
    return len(text)


def save() -> str:
    """Save the active document. If unsaved, write to ~/Documents/UIBridge.docx."""
    doc = _APP.get("doc")
    if doc is None:
        raise RuntimeError("no_document")
    if not getattr(doc, "Path", ""):
        target = Path.home() / "Documents" / "UIBridge.docx"
        doc.SaveAs(str(target))
        return str(target)
    doc.Save()
    return str(Path(getattr(doc, "FullName")))


def quit() -> bool:
    """Quit Word and clear the singleton."""
    if _APP["word"] is not None:
        _APP["word"].Quit()
    _APP["word"] = None
    _APP["doc"] = None
    return True


# Preserve your previous simple API
def count_words(path: Optional[str] = None) -> int:
    fn: Optional[Callable[[Optional[str]], int]] = _word_count
    if fn is None:
        raise RuntimeError("word_count_adapter_missing")
    return int(fn(path))
