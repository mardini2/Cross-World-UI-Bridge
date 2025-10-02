r"""
Goal: Friendly CLI for UIBridge.
- One-time 'setup' wizard for Spotify (stores Client ID via the agent and opens login).
- Top-level aliases so users can type: ui play "drake", ui open youtube, ui search lofi, ui login, ui now, ui pause.
- Auto-start agent if it's not running by launching ../UIBridge/UIBridge.exe and waiting briefly.
- Human outputs by default; still prints compact JSON for API-style commands.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from pathlib import Path

import httpx
import typer

# ---------- app banner / Typer app ----------

app = typer.Typer(
    help="UI Bridge CLI",
    add_completion=False,
    no_args_is_help=True,
)


@app.callback(help="UI Bridge CLI")
def _root_callback() -> None:
    """UI Bridge CLI"""
    return


# ---------- base URL / token helpers ----------


def _host() -> str:
    return os.getenv("UIB_HOST", "127.0.0.1")


def _port() -> int:
    try:
        return int(os.getenv("UIB_PORT", "5025"))
    except Exception:
        return 5025


def _base_url() -> str:
    return f"http://{_host()}:{_port()}"


def _exe_dir() -> Path:
    """Directory of ui.exe when frozen; else the package dir."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _find_agent() -> Path:
    """Locate the agent exe in the release layout."""
    p = _exe_dir()
    candidates = [
        p.parent / "UIBridge" / "UIBridge.exe",  # release zip layout
        p / "UIBridge.exe",  # fallback (dev)
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def _start_agent_if_needed(timeout_s: float = 6.0) -> bool:
    """Ensure the agent is up. Try to start it if needed, then wait briefly."""
    url = _base_url() + "/health"
    try:
        with httpx.Client(timeout=1.0) as c:
            r = c.get(url)
            if r.status_code == 200:
                return True
    except Exception:
        pass

    # Try launching the agent
    try:
        subprocess.Popen([str(_find_agent())], close_fds=True)
    except Exception:
        return False

    # Wait for it to boot
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


# token is shared with the agent via Windows Credential Manager.
# we call the agent for a token if needed so both sides stay in sync.


def _get_or_create_token_via_agent() -> str:
    """
    Ask the agent for (or to mint) the token so CLI and agent always agree.
    Fallback: return empty string if agent is not reachable.
    """
    try:
        with httpx.Client(timeout=3.0) as c:
            r = c.post(_base_url() + "/v1/token", json={"op": "ensure"})
            if r.status_code == 200:
                j = r.json() or {}
                return str(j.get("token", ""))
    except Exception:
        return ""
    return ""


def _headers() -> dict[str, str]:
    """
    Build headers for protected endpoints. If we don't have a token,
    ask the agent to ensure one exists (shared via keyring).
    """
    tok = _get_or_create_token_via_agent()
    return {"X-UIB-Token": tok} if tok else {}


def _need_agent_hint() -> None:
    typer.echo(
        "Agent not reachable. Start it via:\n"
        '  - "Start UIBridge Agent.cmd" (in the unzipped folder)\n'
        "  - or UIBridgeLauncher.exe → Start Agent\n",
        err=True,
    )


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
    If input looks like a URL/domain, ensure it has a scheme.
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
    """Quick health + ping check (tries to auto-start the agent)."""
    ok = _start_agent_if_needed()
    if not ok:
        typer.secho(f"Agent is not responding on {_base_url()}", fg="red", err=True)
        raise typer.Exit(code=1)

    with httpx.Client(timeout=3.0) as c:
        health = c.get(_base_url() + "/health")
        ping = c.get(_base_url() + "/v1/ping", headers=_headers())

    typer.echo(
        {
            "base_url": _base_url(),
            "health": health.status_code,
            "ping": ping.json() if ping.status_code == 200 else {"ok": False},
        }
    )


@app.command()
def ping() -> None:
    """Ping the protected API. Requires a token (created automatically)."""
    ok = _start_agent_if_needed()
    if not ok:
        _need_agent_hint()
        raise typer.Exit(code=2)
    with httpx.Client(timeout=3.0) as c:
        r = c.get(_base_url() + "/v1/ping", headers=_headers())
        typer.echo(r.text)


# ---------- token management ----------

token_app = typer.Typer(
    help="View or reset the shared auth token (stored via keyring)."
)
app.add_typer(token_app, name="token")


@token_app.command("show")
def token_show(
    full: bool = typer.Option(False, "--full", help="Show full token")
) -> None:
    ok = _start_agent_if_needed()
    if not ok:
        _need_agent_hint()
        raise typer.Exit(code=2)
    with httpx.Client(timeout=3.0) as c:
        r = c.get(_base_url() + "/v1/token")
        if r.status_code != 200:
            typer.secho("Token not found.", fg="yellow")
            return
        tok = (r.json() or {}).get("token", "")
        if not tok:
            typer.secho("Token not found.", fg="yellow")
            return
        if full:
            typer.echo(tok)
        else:
            last4 = tok[-4:] if len(tok) >= 4 else tok
            typer.echo(f"Token present. Last 4: {last4}")


@token_app.command("reset")
def token_reset() -> None:
    """Create a fresh token in the shared store (agent + CLI)."""
    ok = _start_agent_if_needed()
    if not ok:
        _need_agent_hint()
        raise typer.Exit(code=2)
    with httpx.Client(timeout=3.0) as c:
        r = c.post(_base_url() + "/v1/token", json={"op": "reset"})
        if r.status_code == 200:
            tok = (r.json() or {}).get("token", "")
            last4 = tok[-4:] if len(tok) >= 4 else tok
            typer.secho(f"Token reset. Last 4: {last4}", fg="green")
        else:
            typer.secho("Failed to reset token.", fg="red", err=True)
            raise typer.Exit(code=2)


# ---------- browser sub-commands ----------

browser_app = typer.Typer(help="Browser control (Edge DevTools)")
app.add_typer(browser_app, name="browser")


@browser_app.command("launch")
def browser_launch() -> None:
    ok = _start_agent_if_needed()
    if not ok:
        _need_agent_hint()
        raise typer.Exit(code=2)
    with httpx.Client(timeout=6.0) as c:
        r = c.post(_base_url() + "/v1/browser/launch", headers=_headers())
        typer.echo(r.text)


@browser_app.command("open")
def browser_open(url: str = typer.Argument(..., help="URL or search text")) -> None:
    """
    Open a URL in a new tab. If you pass plain words (e.g. 'youtube'),
    we turn it into a search automatically.
    """
    ok = _start_agent_if_needed()
    if not ok:
        _need_agent_hint()
        raise typer.Exit(code=2)
    target = _normalize_url_or_search(url)
    with httpx.Client(timeout=8.0) as c:
        r = c.post(
            _base_url() + "/v1/browser/open", headers=_headers(), json={"url": target}
        )
        if r.status_code == 200 and (r.json() or {}).get("ok"):
            typer.echo(r.text)
            return
        # try auto-launch + retry once
        c.post(_base_url() + "/v1/browser/launch", headers=_headers())
        time.sleep(0.8)
        r2 = c.post(
            _base_url() + "/v1/browser/open", headers=_headers(), json={"url": target}
        )
        typer.echo(r2.text)


@browser_app.command("tabs")
def browser_tabs() -> None:
    ok = _start_agent_if_needed()
    if not ok:
        _need_agent_hint()
        raise typer.Exit(code=2)
    with httpx.Client(timeout=5.0) as c:
        r = c.get(_base_url() + "/v1/browser/tabs", headers=_headers())
        typer.echo(r.text)


# ---------- convenient top-level aliases ----------


@app.command("open")
def alias_open(thing: str):
    """Open a URL or search for plain text (same as: browser open)."""
    return browser_open(thing)


@app.command("search")
def alias_search(query: str):
    """Search the web and open results in a new tab."""
    target = _normalize_url_or_search(query)  # becomes a search URL if plain text
    return browser_open(target)


# ---------- spotify commands + setup ----------

spotify_app = typer.Typer(help="Spotify commands")
app.add_typer(spotify_app, name="spotify")


@spotify_app.command("login")
def spotify_login() -> None:
    ok = _start_agent_if_needed()
    if not ok:
        _need_agent_hint()
        raise typer.Exit(code=2)
    login_url = _base_url() + "/auth/spotify/login"
    webbrowser.open(login_url, new=1, autoraise=True)
    typer.echo("Opened Spotify login in your browser.")


@spotify_app.command("play")
def spotify_play(
    query: str = typer.Argument(
        ..., help='Search query, e.g. "lofi" or "drake passions"'
    )
) -> None:
    ok = _start_agent_if_needed()
    if not ok:
        _need_agent_hint()
        raise typer.Exit(code=2)
    with httpx.Client(timeout=8.0) as c:
        r = c.post(
            _base_url() + "/v1/spotify/play", headers=_headers(), json={"q": query}
        )
        typer.echo(r.text)


@spotify_app.command("pause")
def spotify_pause() -> None:
    ok = _start_agent_if_needed()
    if not ok:
        _need_agent_hint()
        raise typer.Exit(code=2)
    with httpx.Client(timeout=6.0) as c:
        r = c.post(_base_url() + "/v1/spotify/pause", headers=_headers())
        typer.echo(r.text)


@spotify_app.command("now")
def spotify_now() -> None:
    ok = _start_agent_if_needed()
    if not ok:
        _need_agent_hint()
        raise typer.Exit(code=2)
    with httpx.Client(timeout=6.0) as c:
        r = c.get(_base_url() + "/v1/spotify/now", headers=_headers())
        typer.echo(r.text)


@app.command("setup")
def setup() -> None:
    """
    First-time setup helper for Spotify:
    - Prompts for your Spotify Client ID (public; no secret).
    - Saves it via the agent.
    - Opens the browser to complete login.
    """
    ok = _start_agent_if_needed()
    if not ok:
        _need_agent_hint()
        raise typer.Exit(code=2)

    typer.echo(
        "Spotify setup:\n"
        "  1) Visit https://developer.spotify.com → Dashboard → Create an app\n"
        "  2) Copy the Client ID (no secret; we use PKCE)\n"
        "  3) Paste it below.\n"
    )
    client_id = typer.prompt("Paste your Spotify Client ID", hide_input=False).strip()
    if not client_id:
        typer.secho("Empty Client ID. Aborting.", fg="red", err=True)
        raise typer.Exit(code=2)

    with httpx.Client(timeout=10.0) as c:
        r = c.post(
            _base_url() + "/v1/spotify/client-id",
            headers=_headers(),
            json={"op": "set", "client_id": client_id},
        )
        j = r.json() if r.status_code == 200 else {"ok": False}
        if not j.get("ok"):
            typer.secho(
                "Could not save Client ID. Is the agent running?", fg="red", err=True
            )
            raise typer.Exit(code=2)

    typer.secho("Saved! A browser will open to link your Spotify account…", fg="green")
    webbrowser.open(_base_url() + "/auth/spotify/login", new=1, autoraise=True)
    typer.echo('When the browser says "Spotify linked", try:  ui play "lofi"')


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
