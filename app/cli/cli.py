"""
Goal: Provide a friendly Typer CLI "ui" that talks to the local agent.
Subcommands: doctor, token, ping, browser, spotify, word, window.
"""

import os
import webbrowser

import httpx
import typer
from loguru import logger

from app.auth.secrets import get_or_create_token, get_token, reset_token
from app.auth.spotify_config import (clear_client_id, get_client_id,
                                     set_client_id)
from app.settings import UIB_HOST, UIB_PORT

app = typer.Typer(help="UI Bridge CLI")
spotify_app = typer.Typer(help="Spotify commands")


def _base() -> str:
    return f"http://{UIB_HOST}:{UIB_PORT}"


@app.command()
def doctor():
    url = f"{_base()}/health"
    try:
        r = httpx.get(url, timeout=5.0)
        r.raise_for_status()
        typer.echo(r.text)
    except Exception as exc:
        logger.error(f"Doctor check failed: {exc}")
        raise typer.Exit(code=1)


@app.command()
def ping():
    url = f"{_base()}/v1/ping"
    tok = get_or_create_token()
    try:
        r = httpx.get(url, headers={"X-UIB-Token": tok}, timeout=5.0)
        r.raise_for_status()
        typer.echo(r.text)
    except Exception as exc:
        logger.error(f"Ping failed: {exc}")
        raise typer.Exit(code=1)


@app.command("token")
def token_cmd(show: bool = typer.Option(False), reset: bool = typer.Option(False)):
    if show and reset:
        typer.echo("Choose either --show or --reset, not both.")
        raise typer.Exit(code=2)
    if reset:
        v = reset_token()
        typer.echo(f"New token set. Last 4: {v[-4:]}")
        return
    if show:
        v = get_token() or get_or_create_token()
        typer.echo(f"Token present. Last 4: {v[-4:]}")
        return
    typer.echo("Use --show to display token tail, or --reset to rotate.")


# -------------------------
# Browser commands
# -------------------------
@app.command()
def browser(
    action: str = typer.Argument(...),
    url: str = typer.Argument("", help="URL for 'open'"),
):
    tok = get_or_create_token()
    if action == "launch":
        r = httpx.post(
            f"{_base()}/v1/browser/launch", headers={"X-UIB-Token": tok}, timeout=8.0
        )
        typer.echo(r.text)
        return
    if action == "open":
        if not url:
            typer.echo("Provide a URL: ui browser open https://example.com")
            raise typer.Exit(code=2)
        r = httpx.post(
            f"{_base()}/v1/browser/open",
            headers={"X-UIB-Token": tok},
            json={"url": url},
            timeout=8.0,
        )
        typer.echo(r.text)
        return
    if action == "tabs":
        r = httpx.get(
            f"{_base()}/v1/browser/tabs", headers={"X-UIB-Token": tok}, timeout=8.0
        )
        typer.echo(r.text)
        return
    typer.echo("browser actions: launch | open <url> | tabs")


# -------------------------
# Spotify commands
# -------------------------
@spotify_app.command("login")
def spotify_login():
    """
    Open browser to authenticate with Spotify using PKCE.
    Needs Client ID in either env (SPOTIFY_CLIENT_ID) or keyring config.
    """
    client_id = os.getenv("SPOTIFY_CLIENT_ID") or get_client_id()
    if not client_id:
        typer.echo(
            "Spotify Client ID missing. Set it with:\n"
            '  python -m app.cli.cli spotify config set-client-id "YOUR_CLIENT_ID"'
        )
        raise typer.Exit(code=2)
    webbrowser.open(f"{_base()}/auth/spotify/login", new=2)


@spotify_app.command("now")
def spotify_now():
    tok = get_or_create_token()
    r = httpx.get(
        f"{_base()}/v1/spotify/now", headers={"X-UIB-Token": tok}, timeout=10.0
    )
    typer.echo(r.text)


@spotify_app.command("play")
def spotify_play(
    query: str = typer.Argument(..., help='Text to search (e.g., "lofi")')
):
    tok = get_or_create_token()
    r = httpx.post(
        f"{_base()}/v1/spotify/play",
        headers={"X-UIB-Token": tok},
        json={"query": query},
        timeout=15.0,
    )
    typer.echo(r.text)
    try:
        j = r.json()
        if j.get("ok") is False:
            typer.echo(
                "Heads up: playback might fail if there is no active device or your account isn't Premium.\n"
                "If the Spotify app isn't open, I try to launch it and wait briefly.\n"
                "If it still fails, start playback for a few seconds in the app, then try again."
            )
    except Exception:
        pass


@spotify_app.command("pause")
def spotify_pause():
    tok = get_or_create_token()
    r = httpx.post(
        f"{_base()}/v1/spotify/pause", headers={"X-UIB-Token": tok}, timeout=10.0
    )
    typer.echo(r.text)


@spotify_app.command("config")
def spotify_config(
    action: str = typer.Argument(
        ..., help="set-client-id | show-client-id | clear-client-id"
    ),
    value: str = typer.Argument("", help="Client ID for set-client-id"),
):
    if action == "set-client-id":
        if not value:
            typer.echo(
                'Provide a Client ID: ui spotify config set-client-id "YOUR_CLIENT_ID"'
            )
            raise typer.Exit(code=2)
        set_client_id(value)
        typer.echo("Client ID saved in Windows Credential Manager.")
        return
    if action == "show-client-id":
        cid = get_client_id() or os.getenv("SPOTIFY_CLIENT_ID") or ""
        if cid:
            tail = cid[-6:] if len(cid) > 6 else cid
            typer.echo(f"Client ID present. Tail: {tail}")
        else:
            typer.echo(
                'No Client ID set. Use: ui spotify config set-client-id "YOUR_CLIENT_ID"'
            )
        return
    if action == "clear-client-id":
        clear_client_id()
        typer.echo("Client ID cleared from Windows Credential Manager.")
        return
    typer.echo("Unknown action. Use: set-client-id | show-client-id | clear-client-id")


app.add_typer(spotify_app, name="spotify")


# -------------------------
# Word + Windows UI
# -------------------------
@app.command()
def word(
    action: str = typer.Argument(...),
    path: str = typer.Argument("", help="Optional doc path for 'count'"),
):
    tok = get_or_create_token()
    if action == "count":
        r = httpx.get(
            f"{_base()}/v1/word/count",
            headers={"X-UIB-Token": tok},
            params={"path": path} if path else None,
            timeout=10.0,
        )
        typer.echo(r.text)
        return
    typer.echo("word actions: count [path]")


@app.command()
def window(
    action: str = typer.Argument(...),
    title: str = typer.Argument("", help="Substring or exact title for 'focus'"),
):
    tok = get_or_create_token()
    if action == "list":
        r = httpx.get(
            f"{_base()}/v1/ui/windows", headers={"X-UIB-Token": tok}, timeout=8.0
        )
        typer.echo(r.text)
        return
    if action == "focus":
        if not title:
            typer.echo("Provide a title substring: ui window focus Notepad")
            raise typer.Exit(code=2)
        r = httpx.post(
            f"{_base()}/v1/ui/focus",
            headers={"X-UIB-Token": tok},
            json={"title_substring": title, "strict": False},
            timeout=8.0,
        )
        typer.echo(r.text)
        return
    typer.echo("window actions: list | focus <title-substring>")


if __name__ == "__main__":
    app()
