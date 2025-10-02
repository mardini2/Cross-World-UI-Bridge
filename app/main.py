"""
UIBridge Agent (FastAPI + Uvicorn)

- Logs to %LOCALAPPDATA%/UIBridge/logs/YYYY-MM-DD.log
- /health is open (no token)
- Uses FastAPI lifespan API (no deprecation warnings)
- Robust runner that avoids uvicorn stdlib logging when frozen
"""

from __future__ import annotations

import os
import secrets
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Callable

from fastapi import Body, FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

# ---------------- Settings ----------------

UIB_HOST = os.getenv("UIB_HOST", "127.0.0.1")
UIB_PORT = int(os.getenv("UIB_PORT", "5025"))

APP_DIR = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "UIBridge"
LOG_DIR = APP_DIR / "logs"
TOKEN_FILE = APP_DIR / "token.txt"
APP_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _get_or_create_token() -> str:
    if TOKEN_FILE.exists():
        t = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if t:
            return t
    t = secrets.token_urlsafe(24)
    TOKEN_FILE.write_text(t, encoding="utf-8")
    return t


UIB_TOKEN = os.getenv("UIB_TOKEN", _get_or_create_token())

# --------------- Logging ------------------


def _configure_logging() -> None:
    """Always log to file; add stderr sink only if it exists (console build)."""
    logger.remove()

    # Ensure folders exist
    APP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_path = LOG_DIR / f"{datetime.utcnow():%Y-%m-%d}.log"

    # File sink (works in --noconsole)
    logger.add(
        str(log_path),
        rotation="10 MB",
        enqueue=True,
        backtrace=True,
        diagnose=True,
        encoding="utf-8",
        level="INFO",
    )

    # Stderr sink only if available (not present in --noconsole bootloader)
    stderr = getattr(sys, "stderr", None)
    if stderr and hasattr(stderr, "write"):
        try:
            logger.add(stderr, level="INFO")
        except Exception:
            # Be defensive — never let logging crash the agent
            pass


_configure_logging()

# --------------- Lifespan -----------------


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    # startup
    logger.info("Agent startup; logs at {}", LOG_DIR)
    APP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        yield
    finally:
        # shutdown
        logger.info("Agent shutdown")


# --------------- FastAPI ------------------

app = FastAPI(title="UIBridge CLI Agent", version="1.0.0", lifespan=app_lifespan)


@app.middleware("http")
async def dispatch(request: Request, call_next: Callable):
    """Allow / and /health without token; require X-UIB-Token for /v1/*."""
    path = request.url.path or "/"
    if path == "/" or path.startswith("/health"):
        return await call_next(request)

    if path.startswith("/v1"):
        hdr = request.headers.get("x-uib-token")
        if hdr != UIB_TOKEN:
            logger.warning("Rejected request: missing/invalid X-UIB-Token")
            return JSONResponse({"error": "unauthorized"}, status_code=401)

    return await call_next(request)


@app.get("/health")
async def health():
    return {"status": "ok", "name": "UIBridge CLI Agent", "port": UIB_PORT}


@app.get("/v1/ping")
async def ping():
    return {"pong": "pong", "token_last4": UIB_TOKEN[-4:]}


# ---- Minimal browser stubs (replace with real handlers) ----


@app.post("/v1/browser/launch")
async def browser_launch():
    return {"ok": True, "pid": 0}


@app.post("/v1/browser/open")
async def browser_open(body: dict = Body(...)):
    url = str(body.get("url") or "").strip()
    return {"ok": bool(url), "url": url}


@app.get("/v1/browser/tabs")
async def browser_tabs():
    return {"tabs": []}


# --------------- Runner -------------------


def main() -> None:
    """Run uvicorn with logging disabled (we use Loguru)."""
    import uvicorn

    # Disable uvicorn’s default logging that touches sys.stderr / isatty
    config = uvicorn.Config(
        app,
        host=UIB_HOST,
        port=UIB_PORT,
        log_config=None,  # avoid dictConfig in frozen --noconsole
        access_log=False,
        loop="asyncio",
    )

    server = uvicorn.Server(config)
    logger.info("Starting Uvicorn on {}:{}", UIB_HOST, UIB_PORT)
    try:
        server.run()  # blocking
    except Exception:
        logger.exception("Fatal error starting UIBridge Agent")
        raise
    finally:
        logger.info(
            "Uvicorn exited (graceful={})", getattr(server, "should_exit", None)
        )


if __name__ == "__main__":
    main()
