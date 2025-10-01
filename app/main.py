"""
Goal: Local FastAPI agent that exposes a secure localhost API for controlling GUI apps.
Endpoints include health, ping, browser (CDP), Spotify, Word COM, and UI automation.
This version uses FastAPI's lifespan hooks (startup/shutdown) to avoid deprecation warnings.
"""

# FastAPI core + response helpers
from fastapi import FastAPI, Request, Body
from fastapi.responses import JSONResponse, HTMLResponse

# Starlette middleware + statuses
from starlette.middleware.base import BaseHTTPMiddleware
from starlette import status

# Utilities
from datetime import datetime, timezone
from contextlib import asynccontextmanager

# Logging (nice format, no secrets)
from loguru import logger

# App settings and services
from app.settings import UIB_PORT, UIB_HOST
from app.services.logs import configure_logging
from app.auth.secrets import get_or_create_token

# Typed models (Pydantic) for stable API contracts
from app.models.schemas import (
    HealthResponse,
    ErrorResponse,
    PingResponse,
    BrowserOpenRequest,
    BrowserOpenResponse,
    SpotifyPlayRequest,
    SpotifyNowResponse,
    WordCountResponse,
    WindowListResponse,
    WindowListItem,
    FocusRequest,
)

# Thin service wrappers
from app.services.browser_service import open_in_browser, launch_edge, get_tabs
from app.services.spotify_service import now as sp_now, play as sp_play, pause as sp_pause
from app.services.word_service import count_words
from app.services.ui_auto_service import windows as list_windows, focus as focus_window

# DB + OAuth router
from app.db import init_db
from app.auth.oauth import router as spotify_oauth_router


# --- Logging comes first so anything during startup gets captured nicely
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Goal: Modern startup/shutdown lifecycle.

    Startup:
      - Initialize the local SQLite DB tables.
      - Log that we're ready.

    Shutdown:
      - Nothing special yet, but this is the place for graceful cleanup.
    """
    await init_db()
    logger.info("Agent started and DB initialized.")
    yield
    # (If we had background tasks, we'd gracefully stop them here.)


# Create the FastAPI app instance with a lifespan handler (no deprecated on_event)
app = FastAPI(title="UI Bridge Agent", version="1.0.0", lifespan=lifespan)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Goal: Protect all routes except /health and /auth/spotify/*
    by requiring the X-UIB-Token header to match our local secret.
    """

    async def dispatch(self, request: Request, call_next):
        # Public endpoints: health + Spotify OAuth handshake
        if request.url.path.startswith("/health") or request.url.path.startswith("/auth/spotify"):
            return await call_next(request)

        # Read header and compare with the stored token
        header = request.headers.get("X-UIB-Token")
        token = get_or_create_token()
        if not header or header != token:
            logger.warning("Rejected request: missing/invalid X-UIB-Token")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content=ErrorResponse(
                    error="auth_missing_or_invalid",
                    message="Provide X-UIB-Token header. Use `ui token --show` to view it.",
                    detail=None,
                ).model_dump(),
            )

        return await call_next(request)


# Wire middleware and routers
app.add_middleware(AuthMiddleware)
app.include_router(spotify_oauth_router)


# -----------------------
# Health & diagnostics
# -----------------------
@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """
    Goal: Simple liveness check for humans and scripts.
    """
    return HealthResponse(
        status="ok",
        name="UI Bridge Agent",
        version=app.version or "0.0.0",
        time_utc=datetime.now(timezone.utc).isoformat(),
        port=UIB_PORT,
    )


@app.get("/v1/ping", response_model=PingResponse)
async def ping() -> PingResponse:
    """
    Goal: Authenticated ping so the CLI can verify secure connectivity.
    """
    token = get_or_create_token()
    return PingResponse(pong="pong", token_last4=token[-4:])


# -----------------------
# Browser / CDP
# -----------------------
@app.post("/v1/browser/open", response_model=BrowserOpenResponse)
async def browser_open(payload: BrowserOpenRequest = Body(...)) -> BrowserOpenResponse:
    """
    Goal: Open a URL via DevTools Protocol (Edge/Chrome launched with --remote-debugging-port=9222).
    """
    ok = await open_in_browser(str(payload.url))
    return BrowserOpenResponse(
        ok=ok,
        message="Opened in default browser via CDP." if ok else "Failed to open.",
        url=str(payload.url),
    )


@app.post("/v1/browser/launch")
async def browser_launch() -> dict:
    """
    Goal: Launch Edge with CDP flags and a disposable profile on localhost.
    """
    pid = launch_edge()
    return {"ok": pid > 0, "pid": pid}


@app.get("/v1/browser/tabs")
async def browser_tabs() -> dict:
    """
    Goal: List tab titles from the running CDP browser.
    """
    tabs = await get_tabs()
    return {"tabs": tabs}


# -----------------------
# Spotify
# -----------------------
@app.get("/v1/spotify/now", response_model=SpotifyNowResponse)
async def spotify_now() -> SpotifyNowResponse:
    """
    Goal: Show what's currently playing (friendly shape).
    """
    d = await sp_now()
    return SpotifyNowResponse(artist=d.get("artist"), track=d.get("track"), is_playing=d.get("is_playing", False))


@app.post("/v1/spotify/play")
async def spotify_play(payload: SpotifyPlayRequest = Body(...)) -> dict:
    """
    Goal: Search and start playback; auto-handles device selection if possible.
    """
    ok = await sp_play(payload.query)
    return {"ok": ok}


@app.post("/v1/spotify/pause")
async def spotify_pause() -> dict:
    """
    Goal: Pause playback where permitted.
    """
    ok = await sp_pause()
    return {"ok": ok}


# -----------------------
# Word COM
# -----------------------
@app.get("/v1/word/count", response_model=WordCountResponse)
async def word_count(path: str | None = None) -> WordCountResponse:
    """
    Goal: Count words in a .doc/.docx via Word COM (Windows-only).
    """
    words = count_words(path)
    return WordCountResponse(path=path, words=words)


# -----------------------
# Windows UI automation
# -----------------------
@app.get("/v1/ui/windows", response_model=WindowListResponse)
async def list_open_windows() -> WindowListResponse:
    """
    Goal: Return titles of open top-level windows.
    """
    titles = list_windows()
    return WindowListResponse(windows=[WindowListItem(title=t) for t in titles])


@app.post("/v1/ui/focus")
async def focus_window_by_title(payload: FocusRequest = Body(...)) -> dict:
    """
    Goal: Bring a window to front by title substring (or exact match if strict=True).
    """
    ok = focus_window(payload.title_substring, payload.strict)
    return {"ok": ok}
