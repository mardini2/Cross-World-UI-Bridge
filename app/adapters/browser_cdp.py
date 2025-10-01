"""
Goal: Control Chromium browsers via DevTools Protocol (CDP) on localhost:9222.
We keep it modest: launch Edge with debugging, open URL, list tabs.
"""

import os
import json
import subprocess
from typing import List, Optional

import httpx
import websockets

from app.settings import CDP_PORT


def launch_edge_with_cdp(extra_args: Optional[list] = None) -> subprocess.Popen:
    """
    Start Microsoft Edge with remote debugging bound to 127.0.0.1:<CDP_PORT>
    and a disposable profile stored under the user's TEMP folder.
    """
    temp_dir = os.environ.get("TEMP") or os.environ.get("TMP") or "."
    profile_dir = os.path.join(temp_dir, "UIBridgeEdgeProfile")

    args = [
        "msedge.exe",
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
    ]
    if extra_args:
        args.extend(extra_args)

    try:
        return subprocess.Popen(args, shell=False)
    except FileNotFoundError:
        edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        if os.path.exists(edge_path):
            args[0] = edge_path
            return subprocess.Popen(args, shell=False)
        args[0] = "chrome.exe"
        return subprocess.Popen(args, shell=False)


async def _get_ws_debugger_url() -> Optional[str]:
    """
    Ask the local CDP /json/version endpoint for the websocket URL.
    """
    url = f"http://127.0.0.1:{CDP_PORT}/json/version"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(url)
            if r.status_code == 200:
                return r.json().get("webSocketDebuggerUrl")
    except Exception:
        return None
    return None


async def open_url(url: str) -> bool:
    """
    Open a new tab to a given URL via CDP. Assumes Edge/Chrome is already
    running with the remote debugging flag.
    """
    ws = await _get_ws_debugger_url()
    if not ws:
        return False
    try:
        async with websockets.connect(ws) as conn:
            await conn.send(json.dumps({
                "id": 1,
                "method": "Target.setDiscoverTargets",
                "params": {"discover": True},
            }))
            await conn.recv()

            await conn.send(json.dumps({
                "id": 2,
                "method": "Target.createTarget",
                "params": {"url": url},
            }))
            await conn.recv()
            return True
    except Exception:
        return False


async def list_tabs() -> List[str]:
    """
    List open tab titles via /json.
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"http://127.0.0.1:{CDP_PORT}/json")
            if r.status_code == 200:
                data = r.json()
                return [d.get("title", "") for d in data if d.get("type") == "page"]
    except Exception:
        return []
    return []
