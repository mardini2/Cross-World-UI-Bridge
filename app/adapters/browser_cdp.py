"""
Goal: Minimal Chromium DevTools (CDP) helpers for Edge on Windows.
- Launch Edge with remote debugging on a chosen port.
- List tabs and open a URL in a new tab.
- Be resilient: if CDP is not up, (re)launch and retry.
"""

from __future__ import annotations

import os  # env for CDP_PORT override
import subprocess  # launch Edge with flags
import time  # tiny sleeps between retries
from pathlib import Path  # path utilities
from typing import List  # typing

import httpx  # HTTP to DevTools endpoints


def _cdp_port() -> int:
    """Return configured CDP port or default 9222."""
    try:
        return int(os.getenv("UIB_CDP_PORT") or os.getenv("CDP_PORT") or "9222")
    except Exception:
        return 9222


def _edge_paths() -> list[Path]:
    """Return candidate paths to msedge.exe."""
    return [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]


def _user_data_dir() -> Path:
    """Return a temporary user-data-dir to avoid interfering with the user's main profile."""
    tmp = os.getenv("TEMP") or os.getenv("TMP") or r"C:\Windows\Temp"
    return Path(tmp) / "UIBridgeEdgeProfile"


def launch_edge_with_cdp(port: int | None = None, kill_existing: bool = True) -> bool:
    """Start Edge with --remote-debugging-port and an isolated profile."""
    port = port or _cdp_port()
    exe = next((p for p in _edge_paths() if p.exists()), None)
    if not exe:
        return False

    if kill_existing:
        # Ensure no old Edge holds the profile/port
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "msedge.exe"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    args = [
        str(exe),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={_user_data_dir()}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    try:
        subprocess.Popen(args, close_fds=True)
    except Exception:
        return False

    # Wait until DevTools answers
    for _ in range(20):  # ~10s
        try:
            with httpx.Client(timeout=0.8) as c:
                r = c.get(f"http://127.0.0.1:{port}/json/version")
                if r.status_code == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def list_tabs() -> List[dict]:
    """Return the list of CDP targets (tabs)."""
    port = _cdp_port()
    with httpx.Client(timeout=1.5) as c:
        r = c.get(f"http://127.0.0.1:{port}/json/list")
        return r.json() if r.status_code == 200 else []


def open_url(url: str) -> bool:
    """Open URL in a new tab; will (re)launch Edge if CDP not ready and retry."""
    port = _cdp_port()
    # First try directly
    try:
        with httpx.Client(timeout=2.5) as c:
            r = c.post(f"http://127.0.0.1:{port}/json/new?{url}")
            if r.status_code == 200:
                return True
    except Exception:
        pass

    # Launch and retry
    if not launch_edge_with_cdp(port=port, kill_existing=False):
        return False
    time.sleep(0.8)
    try:
        with httpx.Client(timeout=2.5) as c:
            r = c.post(f"http://127.0.0.1:{port}/json/new?{url}")
            return r.status_code == 200
    except Exception:
        return False
