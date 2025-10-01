"""
Goal: Implement Spotify OAuth (PKCE) helper endpoints.
We avoid client secret by using PKCE and store tokens + Client ID in Windows Credential Manager.
"""

import base64
import hashlib
import os
import secrets
from typing import Optional

import httpx
import keyring
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.auth.spotify_config import \
    get_client_id  # NEW: keyring-based client ID
from app.settings import SPOTIFY_CLIENT_ID, SPOTIFY_REDIRECT

router = APIRouter(prefix="/auth/spotify", tags=["auth:spotify"])

# Spotify endpoints
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

# Keyring identifiers for tokens
_K_SERVICE = "UIBridgeSpotify"
_K_ACCESS = "access_token"
_K_REFRESH = "refresh_token"


def _code_verifier() -> str:
    return base64.urlsafe_b64encode(os.urandom(60)).decode("utf-8").rstrip("=")


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def _save_tokens(access: str, refresh: Optional[str]) -> None:
    keyring.set_password(_K_SERVICE, _K_ACCESS, access)
    if refresh:
        keyring.set_password(_K_SERVICE, _K_REFRESH, refresh)


def _read_client_id() -> Optional[str]:
    """
    Prefer env var if set; otherwise use keyring.
    Keeping env override is handy for debugging and CI.
    """
    return SPOTIFY_CLIENT_ID or get_client_id()


@router.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    client_id = _read_client_id()
    if not client_id:
        return HTMLResponse(
            "<h3>Spotify Client ID missing.</h3>"
            "<p>Set it with:</p>"
            "<pre>python -m app.cli.cli spotify config set-client-id &quot;YOUR_CLIENT_ID&quot;</pre>",
            status_code=500,
        )

    verifier = _code_verifier()
    challenge = _code_challenge(verifier)
    state = secrets.token_urlsafe(16)

    # Build authorize URL with PKCE
    from urllib.parse import urlencode

    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT,
        "scope": "user-read-playback-state user-modify-playback-state user-read-currently-playing",
        "state": state,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "show_dialog": "false",
    }
    url = f"{AUTH_URL}?{urlencode(params)}"

    # Redirect quickly
    resp_html = f'<a href="{url}">Continue to Spotify login…</a><script>location.href="{url}"</script>'

    resp = HTMLResponse(resp_html)
    resp.set_cookie(
        "pkce_verifier", verifier, max_age=300, httponly=True, samesite="lax"
    )
    resp.set_cookie("oauth_state", state, max_age=300, httponly=True, samesite="lax")
    return resp


@router.get("/callback", response_class=HTMLResponse)
async def callback(request: Request, code: str, state: str):
    cookies = request.cookies or {}
    verifier = cookies.get("pkce_verifier")
    prev_state = cookies.get("oauth_state")

    if not verifier or not prev_state or prev_state != state:
        return HTMLResponse(
            "<h3>State/verifier mismatch. Try login again.</h3>", status_code=400
        )

    client_id = _read_client_id()
    if not client_id:
        return HTMLResponse(
            "<h3>Spotify Client ID missing.</h3>"
            "<p>Set it with:</p>"
            "<pre>python -m app.cli.cli spotify config set-client-id &quot;YOUR_CLIENT_ID&quot;</pre>",
            status_code=500,
        )

    data = {
        "client_id": client_id,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT,
        "code_verifier": verifier,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(TOKEN_URL, data=data)
        if r.status_code != 200:
            return HTMLResponse(
                f"<pre>Token exchange failed:\n{r.text}</pre>", status_code=500
            )

        tok = r.json() or {}
        _save_tokens(tok.get("access_token", ""), tok.get("refresh_token"))

    return HTMLResponse("<h3>Spotify linked. You can close this tab.</h3>")
