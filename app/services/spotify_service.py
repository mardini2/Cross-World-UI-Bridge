"""
Goal: Thin wrapper so FastAPI can call a stable surface, regardless of adapter details.
"""

from __future__ import annotations

from inspect import iscoroutinefunction
from typing import Dict, List, Mapping

from app.adapters import spotify as _sp


async def now() -> Dict:
    return await _sp.now_playing()


async def play(query: str) -> bool:
    return await _sp.play_query(query)


async def pause() -> bool:
    return await _sp.pause()


async def devices() -> List[Dict]:
    return await _sp.list_devices()


# ---- OAuth helpers expected by the agent ----


async def begin_login():
    fn = getattr(_sp, "begin_login", None)
    if not callable(fn):
        raise RuntimeError("spotify adapter has no begin_login")
    return await fn() if iscoroutinefunction(fn) else fn()


async def handle_callback(params: Mapping[str, str] | None = None) -> bool:
    fn = getattr(_sp, "handle_callback", None)
    if not callable(fn):
        raise RuntimeError("spotify adapter has no handle_callback")
    return await fn(params or {}) if iscoroutinefunction(fn) else fn(params or {})
