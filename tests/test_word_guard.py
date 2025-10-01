"""
Goal: Word COM test (guarded) — only asserts import path; we can't guarantee Word is installed here.
"""

import pytest


def test_import_pywin32():
    try:
        import win32com.client  # noqa: F401
    except Exception:
        pytest.skip("pywin32 not available in this environment")
