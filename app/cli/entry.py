"""
UI Bridge CLI

- Automatically sends X-UIB-Token using either:
  - env var UIB_TOKEN, or
  - %LOCALAPPDATA%/UIBridge/token.txt (if present)
- Handy commands:
  - doctor, ping
  - browser launch/open/tabs
  - open/search (top-level aliases)
  - token show / token write
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
from pathlib import Path
from typing import Optional

import httpx
import typer
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(help="UI Bridge CLI", add_completion=False, no_args_is_help=True)

# ---------- config & helpers ----------


def _host() -> str:
    return os.getenv("UIB_HOST", "127.0.0.1")


def _port() -> int:
    try:
        return int(os.getenv("UIB_PORT", "5025"))
    except Exception:
        return 5025


def _base_url() -> str:
    return f"http://{_host()}:{_port()}"


APP_DIR = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "UIBridge"
TOKEN_FILE = APP_DIR / "token.txt"


def _read_token_file() -> Optional[str]:
    try:
        if TOKEN_FILE.exists():
            t = TOKEN_FILE.read_text(encoding="utf-8").strip()
            return t or None
    except Exception:
        pass
    return None


def _token() -> Optional[str]:
    # env wins, else token file
    return os.getenv("UIB_TOKEN") or _read_token_file()


def _client(timeout: float = 8.0) -> httpx.Client:
    headers: dict[str, str] = {}
    tok = _token()
    if tok:
        headers["X-UIB-Token"] = tok
    # /health is public so even without token we can still talk
    return httpx.Client(timeout=timeout, headers=headers)


def _looks_like_url(text: str) -> bool:
    t = text.strip().lower()
    if "://" in t:
        return True
    if t.startswith(("www.", "m.")):
        return True
    if "." in t and " " not in t:
        return True
    return False


def _normalize_url_or_search(text: str) -> str:
    t = text.strip()
    if _looks_like_url(t):
        if "://" not in t:
            t = "https://" + t
        return t
    q = urllib.parse.quote_plus(t)
    return f"https://duckduckgo.com/?q={q}"


# ---------- commands ----------


@app.command()
def doctor() -> None:
    """Check agent health and tokened ping."""
    base = _base_url()

    # health (public)
    try:
        with httpx.Client(timeout=3.0) as c:
            hr = c.get(base + "/health")
            health_ok = hr.status_code == 200
    except Exception as e:
        rprint(f"[red]Health check failed: {e}[/red]")
        raise typer.Exit(code=1)

    # ping (requires token)
    try:
        with _client(timeout=4.0) as c:
            pr = c.get(base + "/v1/ping")
            ping_json = pr.json() if pr.status_code == 200 else {"ok": False}
    except Exception:
        ping_json = {"ok": False}

    tbl = Table(title="UIBridge CLI Agent")
    tbl.add_column("Field")
    tbl.add_column("Value")
    tbl.add_row("Base URL", base)
    tbl.add_row("Health", "ok" if health_ok else "fail")
    tbl.add_row("Ping", json.dumps(ping_json, ensure_ascii=False))
    rprint(Panel(tbl, border_style="green"))

    # Explain if token is missing
    if not _token():
        hint = (
            "[yellow]No token detected.[/yellow]\n"
            'Set it for this shell:  [bold]$env:UIB_TOKEN = Get-Content "$env:LOCALAPPDATA\\UIBridge\\token.txt"[/bold]\n'
            "Or write it via:        [bold]ui token write <token>[/bold]"
        )
        rprint(Panel.fit(hint, border_style="yellow"))


@app.command()
def ping() -> None:
    with _client(timeout=4.0) as c:
        r = c.get(_base_url() + "/v1/ping")
        rprint(
            json.dumps(
                r.json() if r.status_code == 200 else {"ok": False}, ensure_ascii=False
            )
        )


# ----- browser group -----


browser_app = typer.Typer(help="Browser control (Edge DevTools)")
app.add_typer(browser_app, name="browser")


@browser_app.command("launch")
def browser_launch() -> None:
    with _client() as c:
        r = c.post(_base_url() + "/v1/browser/launch")
        rprint(
            json.dumps(
                r.json() if r.status_code == 200 else {"ok": False}, ensure_ascii=False
            )
        )


@browser_app.command("open")
def browser_open(url: str = typer.Argument(..., help="URL or search text")) -> None:
    target = _normalize_url_or_search(url)
    with _client() as c:
        r = c.post(_base_url() + "/v1/browser/open", json={"url": target})
        if r.status_code != 200 or not (r.json() or {}).get("ok"):
            # try to auto-launch, then retry once
            c.post(_base_url() + "/v1/browser/launch")
            time.sleep(0.8)
            r = c.post(_base_url() + "/v1/browser/open", json={"url": target})
        rprint(
            json.dumps(
                r.json() if r.status_code == 200 else {"ok": False}, ensure_ascii=False
            )
        )


@browser_app.command("tabs")
def browser_tabs() -> None:
    with _client() as c:
        r = c.get(_base_url() + "/v1/browser/tabs")
        rprint(
            json.dumps(
                r.json() if r.status_code == 200 else {"tabs": []}, ensure_ascii=False
            )
        )


# ----- convenience aliases -----


@app.command("open")
def alias_open(thing: str):
    """Open a URL or search for plain text (same as: browser open)."""
    return browser_open(thing)


@app.command("search")
def alias_search(query: str):
    """Search the web (DuckDuckGo) and open results in a new tab."""
    target = _normalize_url_or_search(query)
    return browser_open(target)


# ----- token utilities -----


token_app = typer.Typer(help="Token utilities")
app.add_typer(token_app, name="token")


@token_app.command("show")
def token_show(
    full: bool = typer.Option(
        False, "--full", help="Print full token instead of the last 4 chars"
    )
) -> None:
    tok = _token()
    if not tok:
        rprint(
            "[red]No token found.[/red] Start the agent at least once to generate it, or use 'ui token write <token>'."
        )
        raise typer.Exit(code=1)
    out = tok if full else f"...{tok[-4:]}"
    rprint(
        json.dumps(
            {
                "token": out,
                "source": "env" if os.getenv("UIB_TOKEN") else str(TOKEN_FILE),
            },
            ensure_ascii=False,
        )
    )


@token_app.command("write")
def token_write(
    token: str = typer.Argument(
        ..., help="Token string to save to %LOCALAPPDATA%\\UIBridge\\token.txt"
    )
) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token.strip(), encoding="utf-8")
    rprint(json.dumps({"ok": True, "path": str(TOKEN_FILE)}, ensure_ascii=False))


if __name__ == "__main__":
    app()
