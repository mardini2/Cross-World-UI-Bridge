r"""
Goal: Safely compute word count with Word (COM) on Windows.
- SECURITY: Validate/sanitize user-supplied paths before opening.
- Allows common Word doc formats only; blocks UNC paths and non-files.

Notes:
- We use a *raw* docstring to avoid DeprecationWarning from sequences like
  "\\server\share" where "\s" would otherwise be treated as an invalid escape.
"""

from pathlib import Path
from typing import Optional

try:
    import win32com.client as win32  # type: ignore[import-not-found]
except Exception:
    win32 = None  # On non-Windows or missing pywin32, keep module importable

_ALLOWED_EXTS = {".doc", ".docx", ".rtf"}


def _validate_and_resolve_path(raw: str) -> Path:
    """
    Validate and resolve a user-provided path.
    - Must be absolute (or resolvable) and point to an existing regular file.
    - Must not be a UNC path (\\server\\share\\...) to avoid network access surprises.
    - Must have an allowed extension.
    Returns a resolved Path suitable for opening.
    Raises ValueError on any validation failure.
    """
    p = Path(raw)
    try:
        resolved = p.resolve(strict=True)
    except Exception as exc:
        raise ValueError(f"File does not exist or cannot be resolved: {raw}") from exc

    if str(resolved).startswith("\\\\"):
        raise ValueError("UNC/network paths are not allowed.")

    if not resolved.is_file():
        raise ValueError("Path is not a file.")

    if resolved.suffix.lower() not in _ALLOWED_EXTS:
        allowed = ", ".join(sorted(_ALLOWED_EXTS))
        raise ValueError(f"Unsupported file type. Allowed: {allowed}")

    return resolved


def word_count(path: Optional[str] = None) -> int:
    """
    Compute number of words in a document.
    - When 'path' is provided, validates the path and opens the file read-only.
    - When 'path' is None, uses the active Word document if one exists.
    Returns the word count as an int.
    Raises RuntimeError if Word COM is unavailable or validation fails.
    """
    if win32 is None:
        raise RuntimeError(
            "win32com is not available. Install pywin32 and run on Windows."
        )

    word = win32.Dispatch("Word.Application")
    word.Visible = False

    doc = None
    try:
        if path:
            resolved = _validate_and_resolve_path(path)
            # Open read-only, avoid adding to recent files
            # Parameters: FileName, ConfirmConversions, ReadOnly, AddToRecentFiles
            doc = word.Documents.Open(str(resolved), False, True, False)
        else:
            if word.Documents.Count == 0:
                return 0
            doc = word.ActiveDocument

        # 0 -> wdStatisticWords
        count = doc.ComputeStatistics(0)
        return int(count)

    finally:
        if doc is not None and getattr(doc, "Saved", None) is not None:
            try:
                doc.Close(False)
            except Exception:
                pass
        try:
            word.Quit()
        except Exception:
            pass
