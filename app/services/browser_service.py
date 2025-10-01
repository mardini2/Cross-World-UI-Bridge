"""
Goal: Wrapper around browser CDP adapter for the API layer.
"""
from app.adapters.browser_cdp import open_url as cdp_open_url, launch_edge_with_cdp, list_tabs


async def open_in_browser(url: str) -> bool:
    return await cdp_open_url(url)


def launch_edge() -> int:
    proc = launch_edge_with_cdp()
    return proc.pid if proc else -1


async def get_tabs() -> list[str]:
    return await list_tabs()
