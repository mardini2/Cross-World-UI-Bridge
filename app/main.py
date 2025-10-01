"""
Goal: Local FastAPI agent that exposes a secure localhost API for controlling GUI apps.
Endpoints include health, ping, browser (CDP), Spotify, Word COM, and UI automation.
This version uses FastAPI's lifespan hooks (startup/shutdown) to avoid deprecation warnings.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Body, FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.oauth import router as spotify_oauth_router
from app.auth.secrets import get_or_create_token
from app.db import init_db
from app.models.schemas import (
    BrowserOpenRequest,
    BrowserOpenResponse,
    ErrorResponse,
    FocusRequest,
    HealthResponse,
    PingResponse,
    SpotifyNowResponse,
    SpotifyPlayRequest,
    WindowListItem,
    WindowListResponse,
    WordCountResponse,
)
from app.services.browser_service import get_tabs, launch_edge, open_in_browser
from app.services.logs import configure_logging
from app.services.spotify_service import now as sp_now
from app.services.spotify_service import pause as sp_pause
from app.services.spotify_service import play as sp_play
from app.services.ui_auto_service import focus as focus_window
from app.services.ui_auto_service import windows as list_windows
from app.services.word_service import count_words
from app.settings import UIB_PORT

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Agent started and DB initialized.")
    yield


app = FastAPI(title="UIBridge CLI Agent", version="1.0.0", lifespan=lifespan)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/health") or request.url.path.startswith(
            "/auth/spotify"
        ):
            return await call_next(request)
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


app.add_middleware(AuthMiddleware)
app.include_router(spotify_oauth_router)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        name="UIBridge CLI Agent",
        version=app.version or "0.0.0",
        time_utc=datetime.now(timezone.utc).isoformat(),
        port=UIB_PORT,
    )


@app.get("/v1/ping", response_model=PingResponse)
async def ping() -> PingResponse:
    token = get_or_create_token()
    return PingResponse(pong="pong", token_last4=token[-4:])


@app.post("/v1/browser/open", response_model=BrowserOpenResponse)
async def browser_open(payload: BrowserOpenRequest = Body(...)) -> BrowserOpenResponse:
    ok = await open_in_browser(str(payload.url))
    return BrowserOpenResponse(
        ok=ok,
        message="Opened in default browser via CDP." if ok else "Failed to open.",
        url=str(payload.url),
    )


@app.post("/v1/browser/launch")
async def browser_launch() -> dict:
    pid = launch_edge()
    return {"ok": pid > 0, "pid": pid}


@app.get("/v1/browser/tabs")
async def browser_tabs() -> dict:
    tabs = await get_tabs()
    return {"tabs": tabs}


@app.get("/v1/spotify/now", response_model=SpotifyNowResponse)
async def spotify_now() -> SpotifyNowResponse:
    d = await sp_now()
    return SpotifyNowResponse(
        artist=d.get("artist"),
        track=d.get("track"),
        is_playing=d.get("is_playing", False),
    )


@app.post("/v1/spotify/play")
async def spotify_play(payload: SpotifyPlayRequest = Body(...)) -> dict:
    ok = await sp_play(payload.query)
    return {"ok": ok}


@app.post("/v1/spotify/pause")
async def spotify_pause() -> dict:
    ok = await sp_pause()
    return {"ok": ok}


@app.get("/v1/word/count", response_model=WordCountResponse)
async def word_count(path: str | None = None) -> WordCountResponse:
    words = count_words(path)
    return WordCountResponse(path=path, words=words)


@app.get("/v1/ui/windows", response_model=WindowListResponse)
async def list_open_windows() -> WindowListResponse:
    titles = list_windows()
    return WindowListResponse(windows=[WindowListItem(title=t) for t in titles])


@app.post("/v1/ui/focus")
async def focus_window_by_title(payload: FocusRequest = Body(...)) -> dict:
    ok = focus_window(payload.title_substring, payload.strict)
    return {"ok": ok}
