r"""
Goal: Wrap the browser CDP adapter with async-friendly helpers for the API layer.

Why:
- The adapter functions are synchronous. Awaiting them directly causes mypy errors.
- We call them via `anyio.to_thread.run_sync(...)` so FastAPI endpoints can `await`
  these helpers without blocking the event loop.

Functions:
- open_in_browser(url) -> bool
- launch_edge() -> int (PID if a process is returned; -1 otherwise)
- get_tabs() -> list[dict[str, Any]]
"""

from __future__ import annotations

# typing helpers
from typing import Any, Dict, List

# run sync functions in a worker thread so our wrappers are awaitable
from anyio import to_thread

# the underlying (synchronous) adapter functions
from app.adapters.browser_cdp import launch_edge_with_cdp, list_tabs
from app.adapters.browser_cdp import open_url as cdp_open_url


async def open_in_browser(url: str) -> bool:
    """
    Goal: Open the given URL in the Edge instance controlled via CDP.
    Returns True on success, False on failure.
    """
    # Run the sync function in a worker thread and await the result (a bool).
    return await to_thread.run_sync(cdp_open_url, url)


async def launch_edge() -> int:
    """
    Goal: Launch Edge with the proper CDP flags if it's not already running.
    Returns the launched process PID, or -1 if unavailable.
    """
    # Call the sync launcher in a thread. It might return a Popen-like object,
    # or some truthy sentinel. We don't assume a strict type at runtime.
    result = await to_thread.run_sync(launch_edge_with_cdp)

    # Best-effort: fetch a PID attribute if present; otherwise signal failure.
    pid = getattr(result, "pid", None)
    return int(pid) if isinstance(pid, int) else -1


async def get_tabs() -> List[Dict[str, Any]]:
    """
    Goal: Return a list of currently open tabs as dictionaries.
    """
    tabs = await to_thread.run_sync(list_tabs)

    # Normalize to a list[dict[str, Any]] for the API layer.
    if isinstance(tabs, list):
        return [dict(t) for t in tabs]  # tolerant cast of mapping-like items
    return []
