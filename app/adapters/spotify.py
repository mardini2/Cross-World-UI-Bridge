"""
Goal: Spotify Web API control with automatic device handling.
We try to be helpful: if there is no active device, we attempt to
open the Spotify app on Windows, poll for devices for a few seconds,
transfer playback to a good device, and then start playback.

Notes:
- You must link Spotify via OAuth (PKCE). Tokens are read from keyring.
- Playback control typically requires Spotify Premium. 403 -> "premium required".
- We never log tokens or secrets.
"""

import os
import time
from typing import Dict, List, Optional

import httpx
import keyring

# Keyring identifiers for tokens
_K_SERVICE = "UIBridgeSpotify"
_K_ACCESS = "access_token"
_K_REFRESH = "refresh_token"  # reserved for future refresh use

API_BASE = "https://api.spotify.com/v1"


def _access() -> Optional[str]:
    return keyring.get_password(_K_SERVICE, _ACCESS_KEY())


def _ACCESS_KEY() -> str:
    # Small helper to make the key name consistent in one place
    return "access_token"


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _get_devices(client: httpx.AsyncClient, token: str) -> List[Dict]:
    r = await client.get(f"{API_BASE}/me/player/devices", headers=_headers(token))
    if r.status_code != 200:
        return []
    data = r.json() or {}
    return data.get("devices", []) or []


def _maybe_launch_spotify_app() -> None:
    try:
        os.startfile("spotify:")  # URI handler wakes the app (Store version)
        return
    except Exception:
        pass
    try:
        appdata = os.environ.get("APPDATA")
        if appdata:
            exe = os.path.join(appdata, "Spotify", "Spotify.exe")
            if os.path.exists(exe):
                os.startfile(exe)
    except Exception:
        pass


def _pick_device(devs: List[Dict]) -> Optional[str]:
    if not devs:
        return None
    for d in devs:
        if d.get("is_active"):
            return d.get("id")
    for d in devs:
        if (d.get("type") or "").lower() == "computer":
            return d.get("id")
    return (devs[0] or {}).get("id")


async def _ensure_device(
    client: httpx.AsyncClient, token: str, wait_seconds: float = 8.0
) -> Optional[str]:
    devs = await _get_devices(client, token)
    choice = _pick_device(devs)
    if choice:
        return choice

    _maybe_launch_spotify_app()

    steps = int(max(1, wait_seconds / 0.5))
    for _ in range(steps):
        time.sleep(0.5)
        devs = await _get_devices(client, token)
        choice = _pick_device(devs)
        if choice:
            return choice
    return None


async def _transfer_playback(
    client: httpx.AsyncClient, token: str, device_id: str, play: bool = True
) -> bool:
    r = await client.put(
        f"{API_BASE}/me/player",
        headers=_headers(token),
        json={"device_ids": [device_id], "play": play},
    )
    return r.status_code in (200, 204)


async def list_devices() -> List[Dict]:
    """
    Goal: diagnostic helper to show available devices.
    Returns: a list like [{"id": "...","name": "...","type": "...","is_active": true}, ...]
    """
    token = _access()
    if not token:
        return []
    async with httpx.AsyncClient(timeout=10.0) as client:
        devs = await _get_devices(client, token)
        return [
            {
                "id": d.get("id"),
                "name": d.get("name"),
                "type": d.get("type"),
                "is_active": d.get("is_active", False),
            }
            for d in devs
        ]


async def now_playing() -> dict:
    token = _access()
    if not token:
        return {"error": "not_linked"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            f"{API_BASE}/me/player/currently-playing", headers=_headers(token)
        )
        if r.status_code == 204:
            return {"is_playing": False}
        if r.status_code == 403:
            return {"error": "premium_required"}
        if r.status_code != 200:
            return {"error": f"spotify_{r.status_code}"}
        j = r.json() or {}
        item = j.get("item") or {}
        artists = (
            ", ".join([a.get("name", "") for a in (item.get("artists") or [])]) or None
        )
        return {
            "is_playing": j.get("is_playing", False),
            "artist": artists,
            "track": item.get("name"),
        }


async def pause() -> bool:
    token = _access()
    if not token:
        return False

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.put(f"{API_BASE}/me/player/pause", headers=_headers(token))
        if r.status_code in (200, 204):
            return True
        if r.status_code == 403:
            return False
        if r.status_code == 404:
            dev = await _ensure_device(client, token)
            if not dev:
                return False
            ok = await _transfer_playback(client, token, dev, play=False)
            if not ok:
                return False
            r2 = await client.put(
                f"{API_BASE}/me/player/pause", headers=_headers(token)
            )
            return r2.status_code in (200, 204)
        return False


async def play_query(query: str) -> bool:
    token = _access()
    if not token:
        return False

    async with httpx.AsyncClient(timeout=15.0) as client:
        device_id = await _ensure_device(client, token)
        if not device_id:
            return False

        r = await client.get(
            f"{API_BASE}/search",
            headers=_headers(token),
            params={"q": query, "type": "track", "limit": 1},
        )
        if r.status_code == 403:
            return False
        if r.status_code != 200:
            return False

        items = ((r.json() or {}).get("tracks") or {}).get("items") or []
        if not items:
            return False

        uri = items[0].get("uri")
        if not uri:
            return False

        ok = await _transfer_playback(client, token, device_id, play=True)
        if not ok:
            return False

        r2 = await client.put(
            f"{API_BASE}/me/player/play", headers=_headers(token), json={"uris": [uri]}
        )
        return r2.status_code in (200, 204)
