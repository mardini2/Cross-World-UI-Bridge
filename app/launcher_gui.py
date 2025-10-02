"""
Goal: Windows-friendly launcher GUI for UIBridge CLI.
- Starts the agent (UIBridge.exe) and shows a simple status.
- Buttons: "Open CLI Console", "Spotify Setup", "Quit".
- Makes first-run experience obvious for non-technical users.

Notes:
- This is a tiny Tkinter window with a warm cozy look.
- It finds UIBridge.exe next to this exe (../UIBridge/UIBridge.exe when we’re in /ui or launcher folder).
"""

import os  # os utilities to read env vars and paths
import subprocess  # to launch the agent and CLI console
import sys  # to detect PyInstaller "frozen" mode and locate current exe
import time  # small waits while polling agent health
import tkinter as tk  # built-in Tk GUI
import urllib.request  # lightweight HTTP for /health check
from pathlib import Path  # portable path handling
from tkinter import messagebox  # simple message popups

# -----------------------------
# Helpers: locate agent & URLs
# -----------------------------


def _base_dir() -> Path:
    """Return the directory where this program is running."""
    # If frozen by PyInstaller, sys.executable points to the exe directory
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # Else, running from source
    return Path(__file__).resolve().parent


def _find_agent_exe() -> Path:
    """Find UIBridge.exe relative to this launcher."""
    # Typical release layout:
    # UIBridge-Windows/
    #   UIBridge/UIBridge.exe
    #   ui/ui.exe
    #   UIBridgeLauncher.exe  (this)
    base = _base_dir()
    candidates = [
        base.parent / "UIBridge" / "UIBridge.exe",  # if we sit beside /UIBridge
        base / "UIBridge.exe",  # if the launcher is copied inside /UIBridge
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]  # best-guess path (may not exist)


def _api_base() -> str:
    """Compute the agent base URL from env or defaults."""
    host = os.getenv("UIB_HOST", "127.0.0.1")
    port = os.getenv("UIB_PORT", "5025")
    return f"http://{host}:{port}"


def _health_ok() -> bool:
    """Query /health; return True when the agent is up."""
    try:
        with urllib.request.urlopen(_api_base() + "/health", timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


# ---------------------------------
# Actions: start agent, open things
# ---------------------------------


def start_agent() -> bool:
    """Start UIBridge.exe if not already healthy; wait up to ~10s."""
    if _health_ok():
        return True
    agent = _find_agent_exe()
    try:
        # launch detached (no console steal)
        subprocess.Popen([str(agent)], close_fds=True)
    except FileNotFoundError:
        messagebox.showerror(
            "Agent not found",
            f"Could not find agent at:\n{agent}\n\nMake sure the release zip is intact.",
        )
        return False
    except Exception as exc:
        messagebox.showerror("Launch failed", f"Could not start agent:\n{exc}")
        return False

    # Wait for health
    for _ in range(20):  # ~10s
        if _health_ok():
            return True
        time.sleep(0.5)
    return False


def open_cli_console() -> None:
    """Open a persistent console with ui.exe --help."""
    # Open a terminal that stays open (cmd /k)
    base = _base_dir()
    # Try common locations for ui.exe relative to launcher
    candidates = [
        base.parent / "ui" / "ui.exe",
        base / "ui.exe",
    ]
    ui_exe = None
    for c in candidates:
        if c.exists():
            ui_exe = c
            break
    if not ui_exe:
        messagebox.showerror(
            "CLI not found", "Could not find ui.exe next to the launcher."
        )
        return

    try:
        subprocess.Popen(
            ["cmd", "/k", str(ui_exe), "--help"],
            cwd=str(ui_exe.parent),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    except Exception as exc:
        messagebox.showerror("Open CLI failed", f"Could not open CLI console:\n{exc}")


def do_spotify_setup() -> None:
    """Guide the user: open the CLI with 'ui setup' to onboard Spotify."""
    base = _base_dir()
    candidates = [
        base.parent / "ui" / "ui.exe",
        base / "ui.exe",
    ]
    ui_exe = None
    for c in candidates:
        if c.exists():
            ui_exe = c
            break
    if not ui_exe:
        messagebox.showerror(
            "CLI not found", "Could not find ui.exe next to the launcher."
        )
        return

    # Run 'ui setup' in a new console so the user sees prompts
    try:
        subprocess.Popen(
            ["cmd", "/k", str(ui_exe), "setup"],
            cwd=str(ui_exe.parent),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    except Exception as exc:
        messagebox.showerror("Setup failed", f"Could not start Spotify setup:\n{exc}")


# -------------
# Tiny Tk GUI
# -------------


def main() -> None:
    """Build and run the cozy Tk window."""
    # Create window
    root = tk.Tk()
    root.title("UIBridge Launcher")
    root.geometry("420x250")
    root.configure(bg="#fff8f2")  # warm background

    # Title
    title = tk.Label(
        root,
        text="UIBridge Launcher",
        font=("Segoe UI", 18, "bold"),
        bg="#fff8f2",
        fg="#2a2320",
    )
    title.pack(pady=(18, 4))

    # Status label
    status = tk.Label(
        root, text="Agent: checking…", font=("Segoe UI", 11), bg="#fff8f2", fg="#6b5e57"
    )
    status.pack(pady=(0, 14))

    # Buttons frame
    btns = tk.Frame(root, bg="#fff8f2")
    btns.pack(pady=6)

    def refresh_status(ok: bool) -> None:
        status.configure(text=("Agent: running" if ok else "Agent: not running"))
        status.configure(fg=("#0d6f00" if ok else "#9a3324"))

    def on_start():
        ok = start_agent()
        if not ok:
            messagebox.showwarning(
                "Agent not responding",
                "The agent did not come up.\n\nIf you saw a firewall prompt, allow on Private networks.\n"
                "If a popup said 'failed to load Python DLL', install the Microsoft VC++ 2015–2022 x64 runtime.",
            )
        refresh_status(_health_ok())

    def on_cli():
        if not _health_ok() and not start_agent():
            messagebox.showwarning("Agent not running", "Could not start the agent.")
            refresh_status(False)
            return
        refresh_status(True)
        open_cli_console()

    def on_spotify():
        if not _health_ok() and not start_agent():
            messagebox.showwarning("Agent not running", "Could not start the agent.")
            refresh_status(False)
            return
        refresh_status(True)
        do_spotify_setup()

    # Buttons
    b1 = tk.Button(btns, text="Start Agent", width=16, command=on_start)
    b2 = tk.Button(btns, text="Open CLI Console", width=16, command=on_cli)
    b3 = tk.Button(btns, text="Spotify Setup", width=16, command=on_spotify)
    b1.grid(row=0, column=0, padx=8, pady=6)
    b2.grid(row=0, column=1, padx=8, pady=6)
    b3.grid(row=0, column=2, padx=8, pady=6)

    # First paint: check status, try to start quickly
    ok0 = _health_ok()
    refresh_status(ok0)
    if not ok0:
        # try auto-start once on open
        if start_agent():
            refresh_status(True)

    # Footer note
    note = tk.Label(
        root,
        text="Tip: Use 'Open CLI Console' for commands like\nui open https://example.com   or   ui play \"lofi\"",
        font=("Segoe UI", 9),
        bg="#fff8f2",
        fg="#6b5e57",
        justify="center",
    )
    note.pack(pady=(14, 6))

    root.mainloop()


if __name__ == "__main__":
    main()
