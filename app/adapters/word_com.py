r"""
Goal: Safely compute word count with Word (COM) on Windows.
- SECURITY: Validate/sanitize user-supplied paths before opening.
- Allows common Word doc formats only; blocks UNC paths and non-files.

Notes:
- We use a *raw* docstring to avoid DeprecationWarning from sequences like
  "\\server\share" where "\s" would otherwise be treated as an invalid escape.
"""

# stdlib imports
from pathlib import Path  # robust path handling
from typing import Optional  # optional param typing

# third-party imports
try:
    import win32com.client as win32  # Word COM (pywin32)
except Exception:
    win32 = None  # On non-Windows or missing pywin32, keep module importable


# Define allowed extensions (adjust if you want to support more)
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

    # Resolve symlinks/relative segments; require that it exists.
    try:
        resolved = p.resolve(strict=True)
    except Exception as exc:
        raise ValueError(f"File does not exist or cannot be resolved: {raw}") from exc

    # Disallow UNC/network paths (e.g., \\server\share\file.docx)
    if str(resolved).startswith("\\\\"):
        raise ValueError("UNC/network paths are not allowed.")

    # Must be a regular file
    if not resolved.is_file():
        raise ValueError("Path is not a file.")

    # Extension allowlist
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
    # Ensure COM is available (Windows + pywin32 installed)
    if win32 is None:
        raise RuntimeError(
            "win32com is not available. Install pywin32 and run on Windows."
        )

    # Start Word (hidden)
    word = win32.Dispatch("Word.Application")
    word.Visible = False

    doc = None
    try:
        if path:
            # SECURITY: validate the user-provided path before opening
            resolved = _validate_and_resolve_path(path)
            # Open read-only, avoid adding to MRU/recent files
            # Parameters: FileName, ConfirmConversions, ReadOnly, AddToRecentFiles
            doc = word.Documents.Open(
                str(resolved), False, True, False
            )  # type: ignore[arg-type]
        else:
            # No path provided: fall back to active document if one is open
            if word.Documents.Count == 0:
                return 0
            doc = word.ActiveDocument

        # 0 -> wdStatisticWords (per Word constants)
        count = doc.ComputeStatistics(0)
        return int(count)

    finally:
        # Close doc if we opened one
        if doc is not None and getattr(doc, "Saved", None) is not None:
            try:
                doc.Close(False)
            except Exception:
                pass
        # Quit Word
        try:
            word.Quit()
        except Exception:
            pass
