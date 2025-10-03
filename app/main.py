"""
UIBridge Agent (FastAPI + Uvicorn)

Goals
- Keep the agent stable while restoring Chrome/Edge/Spotify/Word controls.
- Auth: /health is open; /v1/* requires X-UIB-Token; /auth/spotify* is open for OAuth redirects.
- Token: /v1/token {op: ensure|reset} so CLI/CI can manage tokens safely.
- Services are optional: return friendly errors if missing, never crash.
- Handle both sync and async service functions.
- NEW: Auto-seed a default Spotify Client ID so users can log in without pasting it,
       while still allowing override via /v1/spotify/client-id.

Notes
- Port kept at 5025 to match your build scripts and CLI.
- Browser service aligns to your async wrappers: open_in_browser / launch_edge / get_tabs.
- Spotify play accepts both "query" and "q".
"""

from __future__ import annotations

import os
import secrets
import sys
import webbrowser
from contextlib import asynccontextmanager
from datetime import datetime
from inspect import iscoroutinefunction
from pathlib import Path
from typing import Any, Callable

from fastapi import Body, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from loguru import logger

# ---------------- Settings ----------------

UIB_HOST = os.getenv("UIB_HOST", "127.0.0.1")
UIB_PORT = int(os.getenv("UIB_PORT", "5025"))

APP_DIR = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "UIBridge"
LOG_DIR = APP_DIR / "logs"
TOKEN_FILE = APP_DIR / "token.txt"
APP_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# NEW: public (safe) default Client ID you asked to distribute to all users.
#      Users may override later via POST /v1/spotify/client-id.
DEFAULT_SPOTIFY_CLIENT_ID = os.getenv(
    "UIB_SPOTIFY_CLIENT_ID",
    "486429421ebf4250bf85f326fd1bef5c",
)


def _get_or_create_token() -> str:
    """Read token from file; if absent, create and persist."""
    if TOKEN_FILE.exists():
        t = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if t:
            return t
    t = secrets.token_urlsafe(24)
    TOKEN_FILE.write_text(t, encoding="utf-8")
    return t


def _reset_token() -> str:
    """Generate and persist a new token."""
    t = secrets.token_urlsafe(24)
    TOKEN_FILE.write_text(t, encoding="utf-8")
    return t


# --------------- Logging ------------------


def _configure_logging() -> None:
    """Always log to file; add stderr sink if available."""
    logger.remove()
    log_path = LOG_DIR / f"{datetime.utcnow():%Y-%m-%d}.log"
    logger.add(
        str(log_path),
        rotation="10 MB",
        enqueue=True,
        backtrace=True,
        diagnose=True,
        encoding="utf-8",
        level="INFO",
    )
    stderr = getattr(sys, "stderr", None)
    if stderr and hasattr(stderr, "write"):
        try:
            logger.add(stderr, level="INFO")
        except Exception:
            # Never let logging crash the agent
            pass


_configure_logging()

# --------------- Optional services --------
# Import optional modules. If not present, endpoints still respond safely.

try:
    # Your async wrappers:
    # open_in_browser(url) -> bool
    # launch_edge() -> int
    # get_tabs() -> list[dict]
    import app.services.browser_service as _browser_svc  # noqa: F401
except Exception:
    _browser_svc = None  # type: ignore[assignment]

try:
    # Your Spotify wrapper (async):
    # now() -> dict, play(query) -> bool, pause() -> bool, devices() -> list[dict]
    import app.services.spotify_service as _spotify_svc  # noqa: F401
except Exception:
    _spotify_svc = None  # type: ignore[assignment]

try:
    # Word COM helper
    import app.services.word_service as _word_svc  # noqa: F401
except Exception:
    _word_svc = None  # type: ignore[assignment]


# --------------- FastAPI ------------------


@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    Startup/shutdown hooks.
    NEW: On startup, if there is no stored Spotify Client ID, seed with DEFAULT_SPOTIFY_CLIENT_ID.
    """
    logger.info("Agent startup; logs at {}", LOG_DIR)
    APP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # --- auto-seed Spotify Client ID if missing ---
    try:
        # local helpers defined below
        current = _kr_get("UIBridge", "spotify_client_id")
        if not (current or "").strip():
            if DEFAULT_SPOTIFY_CLIENT_ID.strip():
                _kr_set(
                    "UIBridge", "spotify_client_id", DEFAULT_SPOTIFY_CLIENT_ID.strip()
                )
                logger.info("Seeded default Spotify Client ID into key store.")
            else:
                logger.warning("DEFAULT_SPOTIFY_CLIENT_ID empty; not seeding.")
        else:
            logger.info("Spotify Client ID already present; skipping seed.")
    except Exception:
        # never crash agent on seeding failure
        logger.exception("Failed to auto-seed Spotify Client ID (non-fatal)")

    yield
    logger.info("Agent shutdown")


app = FastAPI(title="UIBridge CLI Agent", version="1.3.1", lifespan=lifespan)


@app.middleware("http")
async def dispatch(request: Request, call_next: Callable[..., Any]):
    """
    - Allow / and /health without token.
    - Allow /auth/spotify/* without token so OAuth redirects can complete.
    - Require X-UIB-Token for /v1/*.
    """
    path = request.url.path or "/"

    # public endpoints
    if path == "/" or path.startswith("/health") or path.startswith("/auth/spotify"):
        return await call_next(request)

    # protected API
    if path.startswith("/v1"):
        hdr = request.headers.get("x-uib-token")
        if hdr != _get_or_create_token():
            logger.warning("Rejected request: missing/invalid X-UIB-Token")
            return JSONResponse({"error": "unauthorized"}, status_code=401)

    return await call_next(request)


# ---- Health & Ping -----------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "name": "UIBridge CLI Agent", "port": UIB_PORT}


@app.get("/v1/ping")
async def ping() -> dict[str, Any]:
    t = _get_or_create_token()
    return {"pong": "pong", "token_last4": t[-4:]}


# ---- Token management for CLI/CI --------------------------------------------


@app.get("/v1/token")
async def token_get() -> dict[str, Any]:
    """Return the current token (ensures one exists)."""
    return {"token": _get_or_create_token()}


@app.post("/v1/token")
async def token_post(body: dict | None = Body(None)) -> dict[str, Any]:
    """
    Body: {"op": "ensure"} or {"op": "reset"}
    - ensure: returns existing or creates a new one
    - reset: creates and returns a new token (effective immediately)
    """
    op = str((body or {}).get("op", "ensure")).lower()
    if op == "reset":
        return {"token": _reset_token()}
    return {"token": _get_or_create_token()}


# ---- Browser endpoints (Edge/Chrome/CDP) ------------------------------------


def _fallback_launch(browser: str) -> dict[str, Any]:
    """Fallback launcher if service module is missing."""
    try:
        webbrowser.open("about:blank", new=1)
        return {"ok": True, "pid": 0, "browser": browser}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "browser": browser}


def _fallback_open(url: str) -> dict[str, Any]:
    try:
        webbrowser.open(url, new=2)
        return {"ok": True, "url": url}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "url": url, "error": str(e)}


@app.post("/v1/browser/launch")
async def browser_launch(body: dict | None = Body(None)) -> dict[str, Any]:
    browser = (body or {}).get("browser", "edge")
    if _browser_svc:
        fn = getattr(_browser_svc, "launch_edge", None)
        if callable(fn):
            try:
                pid = await fn() if iscoroutinefunction(fn) else fn()
                # If service says "no PID" or negative, still return ok and include fallback pid=0
                pid_int = int(pid or -1)
                if pid_int < 0:
                    _fallback_launch(str(browser))
                    return {"ok": True, "pid": 0, "browser": str(browser)}
                return {"ok": True, "pid": pid_int, "browser": str(browser)}
            except Exception:  # noqa: BLE001
                logger.exception("browser_service.launch_edge error")
                # fallback
                return _fallback_launch(str(browser))
        # legacy names...
        for name in ("cdp_launch", "launch_browser", "edge_launch", "chrome_launch"):
            fn2 = getattr(_browser_svc, name, None)
            if callable(fn2):
                try:
                    pid = (
                        await fn2(str(browser))
                        if iscoroutinefunction(fn2)
                        else fn2(str(browser))
                    )
                    return {"ok": True, "pid": int(pid or 0), "browser": str(browser)}
                except Exception:  # noqa: BLE001
                    logger.exception("browser_service.%s error", name)
                    return _fallback_launch(str(browser))
    return _fallback_launch(str(browser))


@app.post("/v1/browser/open")
async def browser_open(body: dict = Body(...)) -> dict[str, Any]:
    url = str(body.get("url") or "").strip()
    if not url:
        return {"ok": False, "error": "missing url"}

    # Try service first
    if _browser_svc:
        for name in ("open_in_browser", "cdp_open_url", "open_url"):
            fn = getattr(_browser_svc, name, None)
            if callable(fn):
                try:
                    ok = (
                        bool(await fn(url))
                        if iscoroutinefunction(fn)
                        else bool(fn(url))
                    )
                    if ok:
                        return {"ok": True, "url": url}
                    # Service returned False -> fall back below
                except Exception:  # noqa: BLE001
                    logger.exception("browser_service.%s error", name)
                    # Fall through to fallback

    # Fallback if service missing or reported failure
    return _fallback_open(url)


@app.get("/v1/browser/tabs")
async def browser_tabs() -> dict[str, Any]:
    if _browser_svc:
        fn = getattr(_browser_svc, "get_tabs", None)
        if callable(fn):
            try:
                tabs = await fn() if iscoroutinefunction(fn) else fn()
                return {"tabs": tabs if isinstance(tabs, list) else []}
            except Exception:  # noqa: BLE001
                logger.exception("browser_service.get_tabs error")
                return {"tabs": []}
        for name in ("cdp_list_tabs", "list_tabs"):
            fn2 = getattr(_browser_svc, name, None)
            if callable(fn2):
                try:
                    tabs = await fn2() if iscoroutinefunction(fn2) else fn2()
                    out = (
                        [t for t in tabs if isinstance(t, dict)]
                        if isinstance(tabs, list)
                        else []
                    )
                    return {"tabs": out}
                except Exception:  # noqa: BLE001
                    logger.exception("browser_service.%s error", name)
                    return {"tabs": []}
    return {"tabs": []}


# ---- Spotify client-id store (public client id only) -------------------------


# We store the *public* Spotify client_id using keyring if available, else a file.
def _kr_set(service: str, key: str, value: str) -> bool:
    try:
        import keyring

        keyring.set_password(service, key, value)
        return True
    except Exception:
        (APP_DIR / "secrets").mkdir(parents=True, exist_ok=True)
        (APP_DIR / "secrets" / f"{service}.{key}.txt").write_text(
            value, encoding="utf-8"
        )
        return True


def _kr_get(service: str, key: str) -> str | None:
    try:
        import keyring

        v = keyring.get_password(service, key)
        return v or None
    except Exception:
        p = APP_DIR / "secrets" / f"{service}.{key}.txt"
        if p.exists():
            return (p.read_text(encoding="utf-8").strip()) or None
        return None


def _kr_del(service: str, key: str) -> bool:
    try:
        import keyring

        keyring.delete_password(service, key)
        return True
    except Exception:
        p = APP_DIR / "secrets" / f"{service}.{key}.txt"
        try:
            if p.exists():
                p.unlink()
            return True
        except Exception:
            return False


@app.post("/v1/spotify/client-id")
async def spotify_client_id(body: dict = Body(...)) -> dict[str, Any]:
    """
    Body:
      { "op": "set", "client_id": "..." }
      { "op": "clear" }
      or {} -> returns whether a client_id is stored.
    """
    op = str(body.get("op") or "").lower()
    if op == "clear":
        ok = _kr_del("UIBridge", "spotify_client_id")
        return {"ok": ok}
    if op == "set":
        cid = str(body.get("client_id") or "").strip()
        if not cid:
            return {"ok": False, "error": "missing client_id"}
        ok = _kr_set("UIBridge", "spotify_client_id", cid)
        return {"ok": ok}
    current = _kr_get("UIBridge", "spotify_client_id")
    return {"ok": True, "client_id_set": bool(current)}


@app.get("/v1/spotify/client-id")
async def spotify_client_id_get() -> dict[str, Any]:
    current = _kr_get("UIBridge", "spotify_client_id")
    return {"ok": True, "client_id_set": bool(current)}


# ---- Spotify endpoints -------------------------------------------------------


@app.post("/v1/spotify/play")
async def spotify_play(body: dict = Body(...)) -> dict[str, Any]:
    """Accept both {"query": "..."} and {"q": "..."} to match both CLIs."""
    q = (body.get("query") or body.get("q") or "").strip()
    if not q:
        return {"ok": False, "error": "missing query"}
    if _spotify_svc:
        fn = getattr(_spotify_svc, "play", None)
        if callable(fn):
            try:
                ok = bool(await fn(q)) if iscoroutinefunction(fn) else bool(fn(q))
                return {"ok": ok, "query": q}
            except Exception as e:  # noqa: BLE001
                logger.exception("spotify_service.play error")
                return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "spotify_service_missing"}


@app.post("/v1/spotify/pause")
async def spotify_pause() -> dict[str, Any]:
    if _spotify_svc:
        fn = getattr(_spotify_svc, "pause", None)
        if callable(fn):
            try:
                ok = bool(await fn()) if iscoroutinefunction(fn) else bool(fn())
                return {"ok": ok}
            except Exception as e:  # noqa: BLE001
                logger.exception("spotify_service.pause error")
                return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "spotify_service_missing"}


@app.get("/v1/spotify/now")
async def spotify_now() -> dict[str, Any]:
    if _spotify_svc:
        fn = getattr(_spotify_svc, "now", None) or getattr(
            _spotify_svc, "now_playing", None
        )
        if callable(fn):
            try:
                data = await fn() if iscoroutinefunction(fn) else fn()
                return data if isinstance(data, dict) else {"ok": True, "data": data}
            except Exception as e:  # noqa: BLE001
                logger.exception("spotify_service.now error")
                return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "spotify_service_missing"}


@app.get("/v1/spotify/devices")
async def spotify_devices() -> dict[str, Any]:
    if _spotify_svc:
        fn = getattr(_spotify_svc, "devices", None)
        if callable(fn):
            try:
                devs = await fn() if iscoroutinefunction(fn) else fn()
                return {"ok": True, "devices": devs if isinstance(devs, list) else []}
            except Exception as e:  # noqa: BLE001
                logger.exception("spotify_service.devices error")
                return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "spotify_service_missing"}


# OAuth helpers (no return annotations -> avoids FastAPI response model error)
@app.get("/auth/spotify/login")
async def spotify_login():
    """
    Delegate to adapter if it exposes a login URL; otherwise return a friendly 501.
    """
    if _spotify_svc:
        for name in ("begin_login", "login_url"):
            fn = getattr(_spotify_svc, name, None)
            if callable(fn):
                try:
                    resp = await fn() if iscoroutinefunction(fn) else fn()
                    if hasattr(resp, "status_code"):
                        return resp  # FastAPI Response
                    if isinstance(resp, str):
                        return RedirectResponse(url=resp)
                except Exception:  # noqa: BLE001
                    logger.exception("spotify_service.%s error", name)
                    return JSONResponse(
                        {"ok": False, "error": "spotify_login_failed"}, status_code=500
                    )
    return JSONResponse(
        {
            "ok": False,
            "error": "spotify_service_missing",
            "message": "Spotify linking not available.",
        },
        status_code=501,
    )


@app.get("/auth/spotify/callback")
async def spotify_callback(request: Request):
    if _spotify_svc:
        for name in ("handle_callback", "finish_login"):
            fn = getattr(_spotify_svc, name, None)
            if callable(fn):
                try:
                    params = dict(request.query_params)
                    ok = (
                        bool(await fn(params))
                        if iscoroutinefunction(fn)
                        else bool(fn(params))
                    )
                    return JSONResponse({"ok": ok})
                except Exception:  # noqa: BLE001
                    logger.exception("spotify_service.%s error", name)
                    return JSONResponse({"ok": False}, status_code=500)
    return JSONResponse(
        {"ok": False, "error": "spotify_service_missing"}, status_code=501
    )


# ---- Word endpoints ----------------------------------------------------------


@app.post("/v1/word/open")
async def word_open(body: dict = Body(...)) -> dict[str, Any]:
    path = str(body.get("path") or "").strip() or None
    if _word_svc:
        fn = getattr(_word_svc, "open_document", None)
        if callable(fn):
            try:
                ok = bool(await fn(path)) if iscoroutinefunction(fn) else bool(fn(path))
                return {"ok": ok, "path": path or ""}
            except Exception as e:  # noqa: BLE001
                logger.exception("word_service.open_document error")
                return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "word_service_missing"}


@app.post("/v1/word/type")
async def word_type(body: dict = Body(...)) -> dict[str, Any]:
    text = str(body.get("text") or "")
    if _word_svc:
        fn = getattr(_word_svc, "type_text", None)
        if callable(fn):
            try:
                cnt = await fn(text) if iscoroutinefunction(fn) else fn(text)
                return {"ok": True, "count": int(cnt or 0)}
            except Exception as e:  # noqa: BLE001
                logger.exception("word_service.type_text error")
                return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "word_service_missing"}


@app.post("/v1/word/save")
async def word_save() -> dict[str, Any]:
    if _word_svc:
        fn = getattr(_word_svc, "save", None)
        if callable(fn):
            try:
                path = await fn() if iscoroutinefunction(fn) else fn()
                return {"ok": True, "path": str(path or "")}
            except Exception as e:  # noqa: BLE001
                logger.exception("word_service.save error")
                return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "word_service_missing"}


@app.post("/v1/word/quit")
async def word_quit() -> dict[str, Any]:
    if _word_svc:
        fn = getattr(_word_svc, "quit", None)
        if callable(fn):
            try:
                ok = bool(await fn()) if iscoroutinefunction(fn) else bool(fn())
                return {"ok": ok}
            except Exception as e:  # noqa: BLE001
                logger.exception("word_service.quit error")
                return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "word_service_missing"}


# --------------- Runner -------------------


def main() -> None:
    """Run uvicorn with external logging disabled (Loguru handles logs)."""
    import uvicorn

    config = uvicorn.Config(
        app,
        host=UIB_HOST,
        port=UIB_PORT,
        log_config=None,  # avoid dictConfig noise for --noconsole builds
        access_log=False,
        loop="asyncio",
        lifespan="on",
    )

    server = uvicorn.Server(config)
    logger.info("Starting Uvicorn on {}:{}", UIB_HOST, UIB_PORT)
    try:
        server.run()  # blocking
    except Exception:  # noqa: BLE001
        logger.exception("Fatal error starting UIBridge Agent")
        raise
    finally:
        logger.info(
            "Uvicorn exited (graceful={})", getattr(server, "should_exit", None)
        )


if __name__ == "__main__":
    main()
