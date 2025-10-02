"""
Goal: Implement Spotify OAuth (PKCE) helper endpoints, securely.
- Uses PKCE (no client secret).
- Stores tokens and Client ID in Windows Credential Manager (keyring).
- SECURITY: Cookies now set with HttpOnly + SameSite=Lax + Secure (except on localhost for dev).
"""

# stdlib imports
import base64  # encode random bytes to URL-safe base64 for PKCE verifier/challenge
import hashlib  # hash the verifier to produce the PKCE S256 challenge
import os  # read env vars and detect FORCE_COOKIE_SECURE override
import secrets  # generate random state for CSRF protection
from typing import Optional  # for optional types

# third-party imports
import httpx  # async HTTP client for token exchange
import keyring  # Windows Credential Manager storage
from fastapi import APIRouter, Request  # FastAPI router + incoming request
from fastapi.responses import HTMLResponse  # simple HTML responses

# local imports
from app.auth.spotify_config import get_client_id  # keyring-based Client ID retrieval
from app.settings import SPOTIFY_CLIENT_ID  # env-configured defaults
from app.settings import SPOTIFY_REDIRECT

# Create a router for all Spotify auth endpoints under a common prefix and tag.
router = APIRouter(prefix="/auth/spotify", tags=["auth:spotify"])

# Spotify OAuth endpoints (per Spotify docs)
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

# Keyring identifiers (service name + keys)
_K_SERVICE = "UIBridgeSpotify"
_K_ACCESS = "access_token"
_K_REFRESH = "refresh_token"


def _code_verifier() -> str:
    """
    Make a URL-safe random verifier for PKCE.
    Each char is base64url; rstrip trims '=' padding per spec.
    """
    return base64.urlsafe_b64encode(os.urandom(60)).decode("utf-8").rstrip("=")


def _code_challenge(verifier: str) -> str:
    """
    Hash the verifier using SHA-256 (S256) and base64url encode result.
    """
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def _save_tokens(access: str, refresh: Optional[str]) -> None:
    """
    Persist access/refresh tokens in the OS keyring.
    """
    keyring.set_password(_K_SERVICE, _K_ACCESS, access)
    if refresh:
        keyring.set_password(_K_SERVICE, _K_REFRESH, refresh)


def _read_client_id() -> Optional[str]:
    """
    Prefer env var if provided (useful for CI/dev), else read from keyring.
    """
    return SPOTIFY_CLIENT_ID or get_client_id()


@router.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    """
    Start OAuth by redirecting to Spotify authorize endpoint with PKCE.
    SECURITY: Cookies carry 'Secure' except when running on localhost (HTTP).
    """
    # Pull Client ID from env/keyring
    client_id = _read_client_id()
    if not client_id:
        # Return instructive HTML if the user hasn't configured a Client ID.
        return HTMLResponse(
            "<h3>Spotify Client ID missing.</h3>"
            "<p>Set it with:</p>"
            "<pre>ui spotify config set-client-id &quot;YOUR_CLIENT_ID&quot;</pre>",
            status_code=500,
        )

    # Create verifier/challenge and anti-CSRF state
    verifier = _code_verifier()
    challenge = _code_challenge(verifier)
    state = secrets.token_urlsafe(16)

    # Build the authorize URL (response_type=code + PKCE S256)
    from urllib.parse import urlencode  # imported here to keep imports tidy

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

    # Create a minimal redirecting page (so it works even if meta-refresh is blocked)
    resp_html = f'<a href="{url}">Continue to Spotify login…</a><script>location.href="{url}"</script>'
    resp = HTMLResponse(resp_html)

    # Decide whether to set the Secure flag:
    # - For HTTPS (production): Secure=True.
    # - For localhost/127.0.0.1 over HTTP: Secure=False so cookies work in dev.
    host = (request.url.hostname or "").lower()
    is_local = host in {"localhost", "127.0.0.1"}
    force_secure = os.getenv("FORCE_COOKIE_SECURE", "0") == "1"
    secure_flag = (request.url.scheme == "https") or (not is_local) or force_secure

    # Set short-lived cookies with HttpOnly + SameSite=Lax (+ Secure when appropriate)
    resp.set_cookie(
        key="pkce_verifier",
        value=verifier,
        max_age=300,
        httponly=True,
        samesite="lax",
        secure=secure_flag,
        path="/",
    )
    resp.set_cookie(
        key="oauth_state",
        value=state,
        max_age=300,
        httponly=True,
        samesite="lax",
        secure=secure_flag,
        path="/",
    )
    return resp


@router.get("/callback", response_class=HTMLResponse)
async def callback(request: Request, code: str, state: str):
    """
    Complete OAuth: verify state & PKCE, exchange code for tokens, store in keyring.
    """
    # Read cookies safely (if missing, dict() prevents NoneType)
    cookies = request.cookies or {}
    verifier = cookies.get("pkce_verifier")
    prev_state = cookies.get("oauth_state")

    # Basic CSRF/PKCE validation
    if not verifier or not prev_state or prev_state != state:
        return HTMLResponse(
            "<h3>State/verifier mismatch. Try login again.</h3>", status_code=400
        )

    client_id = _read_client_id()
    if not client_id:
        return HTMLResponse(
            "<h3>Spotify Client ID missing.</h3>"
            "<p>Set it with:</p>"
            "<pre>ui spotify config set-client-id &quot;YOUR_CLIENT_ID&quot;</pre>",
            status_code=500,
        )

    # Token request body (PKCE uses client_id + code_verifier instead of client secret)
    data = {
        "client_id": client_id,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT,
        "code_verifier": verifier,
    }

    # Exchange the code for tokens
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(TOKEN_URL, data=data)
        if r.status_code != 200:
            return HTMLResponse(
                f"<pre>Token exchange failed:\n{r.text}</pre>", status_code=500
            )
        tok = r.json() or {}
        _save_tokens(tok.get("access_token", ""), tok.get("refresh_token"))

    # Small success page
    return HTMLResponse("<h3>Spotify linked. You can close this tab.</h3>")
