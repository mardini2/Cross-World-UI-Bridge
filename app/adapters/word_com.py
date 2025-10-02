r"""
Goal: Safely compute word count with Word (COM) on Windows.

Security hardening:
- Canonicalize & validate user-supplied paths before opening.
- Block UNC/network paths (\\server\share\...).
- Allow only known-safe extensions (.doc, .docx, .rtf).
- Optionally sandbox to a trusted root via env var UIBRIDGE_DOC_ROOT.
- Reject Windows-illegal characters in any path component.
- Open documents read-only and avoid adding to MRU/recent files.

Notes:
- Raw docstring avoids DeprecationWarning for sequences like "\\server\share".
"""

from __future__ import annotations

import os
from importlib import import_module
from pathlib import Path
from typing import Any, Optional

# Runtime import of pywin32 client, typed as Any to support None fallback on non-Windows
win32: Any
try:
    win32 = import_module("win32com.client")
except Exception:
    win32 = None  # keeps module importable even without pywin32/Windows

# Allowed Word document extensions
_ALLOWED_EXTS = {".doc", ".docx", ".rtf"}

# Windows-illegal filename characters (not counting path separators)
# https://learn.microsoft.com/windows/win32/fileio/naming-a-file
_FORBIDDEN_CHARS = set('<>:"|?*')


def _validate_and_resolve_path(raw: str) -> Path:
    r"""
    Validate and resolve a user-provided path.

    Steps:
      1) Canonicalize to an absolute real path (raise if missing).
      2) Disallow UNC/network paths (\\server\share\...).
      3) Reject Windows-illegal characters in any path component.
      4) (Optional) If UIBRIDGE_DOC_ROOT is set, require file to be inside it.
      5) Require the path to be a regular file with an allowed extension.
    """
    # 1) Canonicalize (resolves symlinks; strict=True -> must exist)
    try:
        resolved = Path(raw).resolve(strict=True)
    except Exception as exc:
        raise ValueError(f"File does not exist or cannot be resolved: {raw}") from exc

    # 2) Block UNC/network paths (\\server\share\...)
    if str(resolved).startswith("\\\\"):
        raise ValueError("UNC/network paths are not allowed.")

    # 3) Reject illegal characters in any component
    for part in resolved.parts:
        # Skip drive roots like "C:\\"
        if part.endswith(":\\") or part in ("/", "\\"):
            continue
        if any(ch in _FORBIDDEN_CHARS for ch in part):
            raise ValueError(
                "Path contains characters that are not allowed on Windows."
            )

    # 4) Optional sandbox: only allow files under UIBRIDGE_DOC_ROOT (if set)
    doc_root = os.getenv("UIBRIDGE_DOC_ROOT")
    if doc_root:
        try:
            rootp = Path(doc_root).resolve(strict=True)
        except Exception as exc:
            raise ValueError("Configured UIBRIDGE_DOC_ROOT does not exist.") from exc
        try:
            resolved.relative_to(rootp)  # raises ValueError if outside
        except ValueError as exc:
            raise ValueError("Path is outside the allowed document root.") from exc

    # 5) Must be a regular file with an allowed extension
    if not resolved.is_file():
        raise ValueError("Path is not a file.")
    if resolved.suffix.lower() not in _ALLOWED_EXTS:
        allowed = ", ".join(sorted(_ALLOWED_EXTS))
        raise ValueError(f"Unsupported file type. Allowed: {allowed}")

    return resolved


def word_count(path: Optional[str] = None) -> int:
    """
    Compute the number of words in a document.

    - When 'path' is provided, validate/sanitize and open read-only.
    - When 'path' is None, use the active Word document if available.

    Returns:
        int: word count

    Raises:
        RuntimeError: if Word COM is unavailable or validation fails.
    """
    if win32 is None:
        raise RuntimeError(
            "win32com is not available. Install pywin32 and run on Windows."
        )

    # Start Word hidden
    word = win32.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = False  # Disable security prompts

    doc = None
    try:
        if path:
            # SECURITY: validate before opening
            resolved = _validate_and_resolve_path(path)
            
            # Additional security checks
            if not resolved.suffix.lower() in {'.doc', '.docx', '.rtf'}:
                raise ValueError("Only Word documents (.doc, .docx, .rtf) are allowed")
            
            if resolved.stat().st_size > 50 * 1024 * 1024:  # 50MB limit
                raise ValueError("File too large (max 50MB)")
            
            # Open with maximum security restrictions
            doc = word.Documents.Open(
                str(resolved), 
                ConfirmConversions=False,
                ReadOnly=True, 
                AddToRecentFiles=False,
                Revert=False,
                Format=0,  # Auto-detect format
                NoEncodingDialog=True
            )
        else:
            # No path: use the active document if any
            if word.Documents.Count == 0:
                return 0
            doc = word.ActiveDocument

        # 0 => wdStatisticWords
        count = doc.ComputeStatistics(0)
        return int(count) if count is not None else 0

    except Exception as e:
        raise RuntimeError(f"Failed to process document: {str(e)[:100]}") from e
    finally:
        # Close doc if we opened one
        if doc is not None:
            try:
                doc.Close(SaveChanges=False)
            except Exception:
                pass
        # Quit Word
        try:
            word.Quit()
        except Exception:
            pass
        except Exception:
            pass
