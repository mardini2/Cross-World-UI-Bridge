"""
Goal: Friendly CLI for UIBridge.
- One-time 'setup' wizard for Spotify (stores Client ID via keyring and opens login).
- Top-level aliases so users can type: ui play "drake", ui open youtube, ui search lofi, ui login, ui now, ui pause.
- Auto-start agent if it's not running by launching ../UIBridge/UIBridge.exe and waiting briefly.
- Human outputs by default; still prints compact JSON for API-style commands.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Optional

import httpx
import typer
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table

# Make sure the help string includes the exact text tests expect.
app = typer.Typer(
    help="UI Bridge CLI",
    add_completion=False,
    no_args_is_help=True,
)


# Also put it in the callback so it always shows in --help.
@app.callback(help="UI Bridge CLI")
def _root_callback() -> None:
    """
    UI Bridge CLI
    """
    # no-op; description is used by Typer for help rendering
    return


# ---------- base URL helpers ----------


def _host() -> str:
    return os.getenv("UIB_HOST", "127.0.0.1")


def _port() -> int:
    try:
        return int(os.getenv("UIB_PORT", "5025"))
    except Exception:
        return 5025


def _base_url() -> str:
    return f"http://{_host()}:{_port()}"


# ---------- agent bootstrap ----------


def _exe_dir() -> Path:
    # when frozen by PyInstaller, sys.executable points at ui.exe
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _find_agent() -> Path:
    p = _exe_dir()
    candidates = [
        p.parent / "UIBridge" / "UIBridge.exe",  # release zip layout
        p / "UIBridge.exe",  # fallback
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def _start_agent_if_needed(timeout_s: float = 6.0) -> bool:
    url = _base_url() + "/health"
    try:
        with httpx.Client(timeout=1.0) as c:
            r = c.get(url)
            if r.status_code == 200:
                return True
    except Exception:
        pass

    # Try launch the agent
    try:
        subprocess.Popen([str(_find_agent())], close_fds=True)
    except Exception:
        return False

    # Wait briefly for it to boot
    t0 = time.time()
    with httpx.Client(timeout=1.0) as c:
        while time.time() - t0 < timeout_s:
            try:
                r = c.get(url)
                if r.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(0.3)
    return False


# ---------- URL helpers ----------


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
    """
    If input looks like a URL, ensure it has a scheme.
    Otherwise, return a DuckDuckGo search URL for the query.
    """
    t = text.strip()
    if _looks_like_url(t):
        if "://" not in t:
            t = "https://" + t
        return t
    q = urllib.parse.quote_plus(t)
    return f"https://duckduckgo.com/?q={q}"


# ---------- core commands ----------


@app.command()
def doctor() -> None:
    ok = _start_agent_if_needed()
    if not ok:
        rprint(f"[red]Agent is not responding on {_base_url()}[/red]")
        raise typer.Exit(code=1)
    with httpx.Client(timeout=3.0) as c:
        r = c.get(_base_url() + "/health")
        health_ok = r.status_code == 200
        r2 = c.get(_base_url() + "/v1/ping")
        pong = r2.json() if r2.status_code == 200 else {}
    tbl = Table(title="UIBridge CLI Agent")
    tbl.add_column("Field")
    tbl.add_column("Value")
    tbl.add_row("Base URL", _base_url())
    tbl.add_row("Health", "ok" if health_ok else "fail")
    tbl.add_row("Ping", json.dumps(pong))
    rprint(Panel(tbl, border_style="green"))


@app.command()
def ping() -> None:
    ok = _start_agent_if_needed()
    if not ok:
        rprint(f"[red]Agent is not responding on {_base_url()}[/red]")
        raise typer.Exit(code=1)
    with httpx.Client(timeout=3.0) as c:
        r = c.get(_base_url() + "/v1/ping")
        rprint(json.dumps(r.json(), ensure_ascii=False))


# ---------- browser sub-commands ----------

browser_app = typer.Typer(help="Browser control (Edge DevTools)")
app.add_typer(browser_app, name="browser")


@browser_app.command("launch")
def browser_launch() -> None:
    ok = _start_agent_if_needed()
    if not ok:
        rprint("[red]Agent not responding[/red]")
        raise typer.Exit(code=1)
    with httpx.Client(timeout=5.0) as c:
        r = c.post(_base_url() + "/v1/browser/launch")
        rprint(json.dumps(r.json(), ensure_ascii=False))


@browser_app.command("open")
def browser_open(url: str = typer.Argument(..., help="URL or search text")) -> None:
    """
    Open a URL in a new tab. If you pass plain words (e.g. 'youtube'),
    we turn it into a search automatically.
    """
    ok = _start_agent_if_needed()
    if not ok:
        rprint("[red]Agent not responding[/red]")
        raise typer.Exit(code=1)
    target = _normalize_url_or_search(url)
    with httpx.Client(timeout=8.0) as c:
        r = c.post(_base_url() + "/v1/browser/open", json={"url": target})
        data = r.json() if r.status_code == 200 else {"ok": False}
        if not data.get("ok"):
            # try auto-launch + retry once
            c.post(_base_url() + "/v1/browser/launch")
            time.sleep(0.8)
            r2 = c.post(_base_url() + "/v1/browser/open", json={"url": target})
            data = r2.json() if r2.status_code == 200 else {"ok": False}
        rprint(json.dumps(data, ensure_ascii=False))


@browser_app.command("tabs")
def browser_tabs() -> None:
    ok = _start_agent_if_needed()
    if not ok:
        rprint("[red]Agent not responding[/red]")
        raise typer.Exit(code=1)
    with httpx.Client(timeout=5.0) as c:
        r = c.get(_base_url() + "/v1/browser/tabs")
        rprint(json.dumps(r.json(), ensure_ascii=False))


# ---------- convenient top-level aliases ----------


@app.command("open")
def alias_open(thing: str):
    """Open a URL or search for plain text (same as: browser open)."""
    return browser_open(thing)


@app.command("search")
def alias_search(query: str):
    """Search the web (DuckDuckGo) and open results in a new tab."""
    target = _normalize_url_or_search(query)  # will become a search URL
    return browser_open(target)


# ---------- spotify commands + setup ----------

spotify_app = typer.Typer(help="Spotify commands")
app.add_typer(spotify_app, name="spotify")


@spotify_app.command("config")
def spotify_config_set_client_id(
    set_client_id: Optional[str] = typer.Option(
        None,
        "--set-client-id",
        help='Store your public Spotify "Client ID" (PKCE) in Windows Credential Manager.',
    ),
    clear: bool = typer.Option(False, "--clear", help="Clear the stored Client ID"),
) -> None:
    ok = _start_agent_if_needed()
    if not ok:
        rprint("[red]Agent not responding[/red]")
        raise typer.Exit(code=1)
    with httpx.Client(timeout=6.0) as c:
        if clear:
            r = c.post(_base_url() + "/v1/spotify/client-id", json={"op": "clear"})
            rprint(json.dumps(r.json(), ensure_ascii=False))
            return
        if set_client_id:
            r = c.post(
                _base_url() + "/v1/spotify/client-id",
                json={"op": "set", "client_id": set_client_id},
            )
            rprint(json.dumps(r.json(), ensure_ascii=False))
            return
    rprint("Nothing to do. Use --set-client-id or --clear.")


@spotify_app.command("login")
def spotify_login() -> None:
    ok = _start_agent_if_needed()
    if not ok:
        rprint("[red]Agent not responding[/red]")
        raise typer.Exit(code=1)
    login_url = _base_url() + "/auth/spotify/login"
    webbrowser.open(login_url)
    rprint(
        "[green]A browser tab was opened for Spotify login.[/green] When it says 'Spotify linked', return here."
    )


@spotify_app.command("play")
def spotify_play(
    query: str = typer.Argument(
        ..., help='Search query, e.g. "lofi" or "drake passions"'
    )
) -> None:
    ok = _start_agent_if_needed()
    if not ok:
        rprint("[red]Agent not responding[/red]")
        raise typer.Exit(code=1)
    with httpx.Client(timeout=8.0) as c:
        r = c.post(_base_url() + "/v1/spotify/play", json={"q": query})
        rprint(json.dumps(r.json(), ensure_ascii=False))


@spotify_app.command("pause")
def spotify_pause() -> None:
    ok = _start_agent_if_needed()
    if not ok:
        rprint("[red]Agent not responding[/red]")
        raise typer.Exit(code=1)
    with httpx.Client(timeout=6.0) as c:
        r = c.post(_base_url() + "/v1/spotify/pause")
        rprint(json.dumps(r.json(), ensure_ascii=False))


@spotify_app.command("now")
def spotify_now() -> None:
    ok = _start_agent_if_needed()
    if not ok:
        rprint("[red]Agent not responding[/red]")
        raise typer.Exit(code=1)
    with httpx.Client(timeout=6.0) as c:
        r = c.get(_base_url() + "/v1/spotify/now")
        rprint(json.dumps(r.json(), ensure_ascii=False))


@app.command("setup")
def setup() -> None:
    """
    First-time setup helper for Spotify:
    - Prompts for your Spotify Client ID (public; no secret).
    - Saves it to Windows Credential Manager via the agent.
    - Opens the browser to complete login.
    """
    ok = _start_agent_if_needed()
    if not ok:
        rprint("[red]Agent not responding[/red]")
        raise typer.Exit(code=1)

    rprint(
        Panel.fit(
            "[bold]Spotify setup[/bold]\n"
            "1) Visit https://developer.spotify.com -> Dashboard -> Create an app\n"
            "2) Copy the [bold]Client ID[/bold]. (No secret needed; we use PKCE)\n"
            "3) Paste it when prompted below.\n",
            border_style="magenta",
        )
    )
    client_id = typer.prompt("Paste your Spotify Client ID", hide_input=False)

    with httpx.Client(timeout=10.0) as c:
        r = c.post(
            _base_url() + "/v1/spotify/client-id",
            json={"op": "set", "client_id": client_id},
        )
        j = r.json() if r.status_code == 200 else {"ok": False}
        if not j.get("ok"):
            rprint("[red]Could not save Client ID. Is the agent running?[/red]")
            raise typer.Exit(code=2)

    rprint("[green]Saved![/green] A browser will open to link your Spotify account…")
    webbrowser.open(_base_url() + "/auth/spotify/login")
    rprint('When the browser says "Spotify linked", try:  [bold]ui play "lofi"[/bold]')


# Top-level aliases for Spotify
@app.command("play")
def alias_play(query: str):
    return spotify_play(query)


@app.command("pause")
def alias_pause():
    return spotify_pause()


@app.command("now")
def alias_now():
    return spotify_now()


@app.command("login")
def alias_login():
    return spotify_login()
