r"""
Goal
- Provide async-friendly wrappers around your synchronous CDP adapter so FastAPI endpoints can await safely.

Implements
- open_in_browser(url) -> bool
- launch_edge() -> int
- get_tabs() -> list[dict[str, Any]]

Notes
- Uses anyio.to_thread to call sync adapter functions without blocking the loop.
- Maps to your adapter functions in app.adapters.browser_cdp.
"""

from __future__ import annotations

from typing import Any, Dict, List

from anyio import to_thread

from app.adapters.browser_cdp import launch_edge_with_cdp, list_tabs
from app.adapters.browser_cdp import open_url as cdp_open_url


async def open_in_browser(url: str) -> bool:
    """Open the given URL in the Edge/Chrome instance controlled via CDP."""
    return await to_thread.run_sync(cdp_open_url, url)


async def launch_edge() -> int:
    """
    Launch Edge with CDP flags if not already running.
    Returns a PID if available, or -1.
    """
    result = await to_thread.run_sync(launch_edge_with_cdp)
    pid = getattr(result, "pid", None)
    return int(pid) if isinstance(pid, int) else -1


async def get_tabs() -> List[Dict[str, Any]]:
    """Return a list of open tabs as dictionaries."""
    tabs = await to_thread.run_sync(list_tabs)
    if isinstance(tabs, list):
        return [dict(t) for t in tabs if isinstance(t, dict)]
    return []
