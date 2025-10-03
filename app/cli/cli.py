r"""
Goal: Friendly, typed CLI for UIBridge.

- Export `app` (tests import this).
- Show "UI Bridge CLI" in --help output (tests assert this).
- Use httpx (typed) instead of requests to satisfy mypy.
- Token ops use /v1/token so CI can ensure/reset safely.
- Spotify 'play' sends {"query": "..."}; Agent also accepts {"q": "..."}.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import typer

app = typer.Typer(
    help="UI Bridge CLI",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _host() -> str:
    return os.getenv("UIB_HOST", "127.0.0.1")


def _port() -> int:
    try:
        return int(os.getenv("UIB_PORT", "5025"))
    except Exception:
        return 5025


def _base_url() -> str:
    return os.getenv("UIB_URL", f"http://{_host()}:{_port()}")


BASE_URL = _base_url()
APP_NAME = "UIBridge"
TOKEN_PATH = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / APP_NAME / "token.txt"


def _headers() -> Dict[str, str]:
    tok = os.getenv("UIB_TOKEN")
    if not tok and TOKEN_PATH.exists():
        tok = TOKEN_PATH.read_text(encoding="utf-8").strip()
    return {"X-UIB-Token": tok or ""}


def _get(path: str) -> httpx.Response:
    with httpx.Client(timeout=10.0, headers=_headers()) as c:
        return c.get(f"{BASE_URL}{path}")


def _post(path: str, payload: Dict[str, Any] | None = None) -> httpx.Response:
    with httpx.Client(timeout=15.0, headers=_headers()) as c:
        return c.post(f"{BASE_URL}{path}", json=payload or {})


# Make sure help text includes the exact phrase the test expects
@app.callback(help="UI Bridge CLI")
def _root_callback() -> None:  # noqa: D401 - short help callback
    """Root callback for the CLI."""
    return None


# -----------------------
# Basic
# -----------------------
@app.command("health")
def health() -> None:
    with httpx.Client(timeout=5.0) as c:
        r = c.get(f"{BASE_URL}/health")
        typer.echo(json.dumps(r.json(), indent=2))


@app.command("token")
def token(
    op: Optional[str] = typer.Option(None, help="'show', 'ensure', or 'reset'")
) -> None:
    if op in (None, "show", "ensure"):
        r = _post("/v1/token", {"op": "ensure"})
    elif op == "reset":
        r = _post("/v1/token", {"op": "reset"})
    else:
        typer.echo("invalid op")
        raise typer.Exit(2)
    data = r.json()
    if "token" in data:
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(data["token"], encoding="utf-8")
    typer.echo(json.dumps(data, indent=2))


@app.command("doctor")
def doctor() -> None:
    try:
        with httpx.Client(timeout=3.0) as c:
            h = c.get(f"{BASE_URL}/health").json()
    except Exception as e:  # noqa: BLE001
        typer.echo(json.dumps({"ok": False, "error": f"health: {e}"}, indent=2))
        raise typer.Exit(1)
    try:
        tok = _post("/v1/token", {"op": "ensure"}).json().get("token")
        ok_tok = bool(tok)
    except Exception as e:  # noqa: BLE001
        ok_tok = False
        typer.echo(json.dumps({"ok": False, "error": f"token: {e}"}, indent=2))
    typer.echo(json.dumps({"ok": True, "health": h, "token_present": ok_tok}, indent=2))


# -----------------------
# Browser
# -----------------------
browser = typer.Typer(help="Browser controls (Edge/Chrome via CDP if available)")
app.add_typer(browser, name="browser")


@browser.command("launch")
def browser_launch(
    browser_name: str = typer.Option("edge", help="edge or chrome")
) -> None:
    r = _post("/v1/browser/launch", {"browser": browser_name})
    typer.echo(json.dumps(r.json(), indent=2))


@browser.command("open")
def browser_open(url: str) -> None:
    r = _post("/v1/browser/open", {"url": url})
    typer.echo(json.dumps(r.json(), indent=2))


@browser.command("tabs")
def browser_tabs() -> None:
    r = _get("/v1/browser/tabs")
    typer.echo(json.dumps(r.json(), indent=2))


# -----------------------
# Spotify
# -----------------------
spotify = typer.Typer(help="Spotify controls (requires service configuration)")
app.add_typer(spotify, name="spotify")


@spotify.command("client-id")
def spotify_client_id(
    client_id: Optional[str] = typer.Option(None), clear: bool = False
) -> None:
    payload: Dict[str, Any] = {}
    if clear:
        payload = {"op": "clear"}
    elif client_id:
        payload = {"op": "set", "client_id": client_id}
    r = _post("/v1/spotify/client-id", payload or {})
    typer.echo(json.dumps(r.json(), indent=2))


@spotify.command("login")
def spotify_login() -> None:
    with httpx.Client(timeout=10.0, headers=_headers(), follow_redirects=False) as c:
        r = c.get(f"{BASE_URL}/auth/spotify/login")
        if 300 <= r.status_code < 400:
            typer.echo(
                json.dumps(
                    {"ok": True, "login_url": r.headers.get("Location")}, indent=2
                )
            )
        else:
            typer.echo(json.dumps(r.json(), indent=2))


@spotify.command("play")
def spotify_play(query: str) -> None:
    r = _post("/v1/spotify/play", {"query": query})
    typer.echo(json.dumps(r.json(), indent=2))


@spotify.command("pause")
def spotify_pause() -> None:
    r = _post("/v1/spotify/pause")
    typer.echo(json.dumps(r.json(), indent=2))


@spotify.command("now")
def spotify_now() -> None:
    r = _get("/v1/spotify/now")
    typer.echo(json.dumps(r.json(), indent=2))


# -----------------------
# Word
# -----------------------
word = typer.Typer(help="Microsoft Word automation (Windows only)")
app.add_typer(word, name="word")


@word.command("open")
def word_open(
    path: Optional[str] = typer.Option(None, help="Path to .docx; new doc if omitted")
) -> None:
    r = _post("/v1/word/open", {"path": path or ""})
    typer.echo(json.dumps(r.json(), indent=2))


@word.command("type")
def word_type(text: str) -> None:
    r = _post("/v1/word/type", {"text": text})
    typer.echo(json.dumps(r.json(), indent=2))


@word.command("save")
def word_save() -> None:
    r = _post("/v1/word/save")
    typer.echo(json.dumps(r.json(), indent=2))


@word.command("quit")
def word_quit() -> None:
    r = _post("/v1/word/quit")
    typer.echo(json.dumps(r.json(), indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
