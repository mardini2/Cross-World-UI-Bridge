"""
UIBridge Spotify adapter (PKCE + Web API control)

Goals
- Provide OAuth (PKCE) helpers the agent expects:
    begin_login() -> str (authorization URL)
    handle_callback(params: Mapping[str, str]) -> bool (exchanges code for tokens)
- Provide playback helpers used by the service:
    now_playing(), play_query(query), pause(), list_devices()
- Robust device handling: launch app if needed, poll, transfer playback, then play.
- Never log tokens. Store tokens in keyring with file fallback.

Where things are stored
- Client ID: keyring service "UIBridge", key "spotify_client_id"
  (fallback: %LOCALAPPDATA%/UIBridge/secrets/UIBridge.spotify_client_id.txt)
- Access/Refresh tokens (primary):
    service "UIBridge", keys "spotify_access_token" / "spotify_refresh_token"
  (compat read-only, if present): service "UIBridgeSpotify", key "access_token"
- File fallback token cache: %LOCALAPPDATA%/UIBridge/secrets/spotify_tokens.json
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

import httpx

API_BASE = "https://api.spotify.com/v1"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
REDIRECT_URI = "http://127.0.0.1:5025/auth/spotify/callback"

# --- paths ---
APP_DIR = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "UIBridge"
SECRETS_DIR = APP_DIR / "secrets"
SECRETS_DIR.mkdir(parents=True, exist_ok=True)
PKCE_STATE_FILE = SECRETS_DIR / "spotify_pkce.json"
TOKENS_FILE = SECRETS_DIR / "spotify_tokens.json"

# ---------- keyring helpers (with file fallback) ----------


def _kr_set(key: str, value: str) -> bool:
    """
    Store token in keyring service 'UIBridge', and mirror to TOKENS_FILE.
    """
    ok = True
    try:
        import keyring  # runtime import; if missing, fallback below

        keyring.set_password("UIBridge", key, value)
    except Exception:
        ok = True  # still ok; we'll write the file below

    # keep a json fallback for debug / portability
    data = _read_json(TOKENS_FILE)
    data[key] = value
    TOKENS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return ok


def _kr_get(key: str) -> Optional[str]:
    # primary
    try:
        import keyring

        v = keyring.get_password("UIBridge", key)
        if v:
            return v
    except Exception:
        pass

    # compat: old service/key
    if key == "spotify_access_token":
        try:
            import keyring

            v2 = keyring.get_password("UIBridgeSpotify", "access_token")
            if v2:
                return v2
        except Exception:
            pass

    # file fallback
    data = _read_json(TOKENS_FILE)
    v3 = data.get(key)
    return str(v3) if v3 else None


def _kr_get_client_id() -> Optional[str]:
    # primary (agent writes here)
    try:
        import keyring

        cid = keyring.get_password("UIBridge", "spotify_client_id")
        if cid:
            return cid
    except Exception:
        pass

    # fallback file (agent’s main also supports this style)
    p = SECRETS_DIR / "UIBridge.spotify_client_id.txt"
    if p.exists():
        t = p.read_text(encoding="utf-8").strip()
        if t:
            return t
    return None


def _read_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


# ---------- PKCE helpers ----------


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _new_code_verifier_challenge() -> Tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(64))  # 43-128 chars
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = _b64url(digest)
    return verifier, challenge


# ---------- OAuth API expected by the agent ----------


def begin_login() -> str:
    """
    Returns an authorization URL. The agent will redirect the browser there.
    We persist {state, code_verifier} to complete the callback exchange.
    """
    client_id = _kr_get_client_id()
    if not client_id:
        raise RuntimeError("spotify client_id not set")

    state = _b64url(secrets.token_bytes(24))
    verifier, challenge = _new_code_verifier_challenge()

    PKCE_STATE_FILE.write_text(
        json.dumps({"state": state, "code_verifier": verifier}, ensure_ascii=False),
        encoding="utf-8",
    )

    scopes = [
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-currently-playing",
        "app-remote-control",
        "streaming",
    ]
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "state": state,
        "scope": " ".join(scopes),
        "show_dialog": "false",
    }
    q = httpx.QueryParams(params)
    return f"{AUTH_URL}?{q}"


def handle_callback(params: Mapping[str, str]) -> bool:
    """
    Exchanges ?code=... for tokens via PKCE and stores them.
    """
    if params.get("error"):
        return False
    code = params.get("code")
    state = params.get("state")
    if not code or not state:
        return False

    try:
        saved = json.loads(PKCE_STATE_FILE.read_text(encoding="utf-8"))
        saved_state = saved.get("state")
        code_verifier = saved.get("code_verifier")
    except Exception:
        return False

    if not code_verifier or state != saved_state:
        return False

    client_id = _kr_get_client_id()
    if not client_id:
        return False

    data = {
        "client_id": client_id,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    }

    with httpx.Client(timeout=15.0) as c:
        r = c.post(
            TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code != 200:
            return False
        tok = r.json() or {}

    access = tok.get("access_token")
    refresh = tok.get("refresh_token")
    if not access or not refresh:
        return False

    _kr_set("spotify_access_token", str(access))
    _kr_set("spotify_refresh_token", str(refresh))

    try:
        PKCE_STATE_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    return True


# ---------- Web API helpers used by the service ----------


def _access() -> Optional[str]:
    return _kr_get("spotify_access_token")


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
        os.startfile("spotify:")  # wake the app if URI handler is registered
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
        time.sleep(0.5)  # simple poll; small enough to be fine in a worker thread
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
    Diagnostic helper: returns [{"id","name","type","is_active"}, ...]
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
                "is_active": bool(d.get("is_active")),
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
            "is_playing": bool(j.get("is_playing")),
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
