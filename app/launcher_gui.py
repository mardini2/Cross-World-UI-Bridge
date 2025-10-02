r"""
Goal: A tiny Windows launcher for UIBridge CLI with a friendly GUI.
- Start/stop (start only) the agent, open the CLI, install PATH shim, and enable/disable startup.
- Shows live agent health (polls /health).
- Works from the packaged bundle layout produced by Release CI.

Bundle layout (ZIP root after extraction):
  UIBridge-Windows\
    Start UIBridge Agent.cmd
    Open UIBridge CLI.cmd
    install_agent_startup.ps1
    uninstall_agent_startup.ps1
    install_cli_shim.ps1
    README.txt
    UIBridgeLauncher\UIBridgeLauncher.exe   <- this file, compiled
    UIBridge\UIBridge.exe                   <- agent
    ui\ui.exe                               <- CLI

Notes:
- No third-party imports; only stdlib (so mypy is happier and the EXE is slimmer).
- Avoids platform-specific type:ignore by using subprocess instead of os.startfile().
- All actions are defensive: verify files exist, show clear error messages if not.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
from pathlib import Path
from tkinter import messagebox

# -----------------------------
# Paths & constants
# -----------------------------

HOST = "127.0.0.1"
PORT = 5025
HEALTH_URL = f"http://{HOST}:{PORT}/health"


# In PyInstaller, sys.executable points to the EXE. When running from source, __file__ works.
def _bundle_root() -> Path:
    """Return the expected ZIP root (the parent of the folder that contains this launcher EXE)."""
    exe_dir = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent
    )
    return exe_dir.parent


ROOT = _bundle_root()
AGENT_EXE = ROOT / "UIBridge" / "UIBridge.exe"
UI_EXE = ROOT / "ui" / "ui.exe"
SCRIPTS_DIR = ROOT  # scripts are copied to ZIP root by the Release workflow
LOGS_DIR = Path(
    (Path.home() / "AppData" / "Local" / "UIBridge" / "logs")
)  # matches app-side default

# Creation flags to detach child processes from our console/window (Windows values)
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
SPAWN_FLAGS = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


# -----------------------------
# Helpers (no mypy ignores)
# -----------------------------


def is_agent_running(timeout: float = 1.0) -> bool:
    """True if GET /health returns HTTP 200."""
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_agent_and_check() -> bool:
    """
    Start the agent if not already running. Return True if running after start.
    Uses subprocess to avoid platform-specific os.startfile type issues.
    """
    if is_agent_running():
        return True

    if not AGENT_EXE.exists():
        messagebox.showerror(
            "UIBridge Launcher",
            f"Agent not found:\n{AGENT_EXE}\n\nMake sure the ZIP was extracted intact.",
        )
        return False

    try:
        # Launch detached so we don't block the GUI. Working dir = agent folder.
        subprocess.Popen(
            [str(AGENT_EXE)],
            cwd=str(AGENT_EXE.parent),
            creationflags=SPAWN_FLAGS,
            shell=False,
        )
    except Exception as exc:
        messagebox.showerror("UIBridge Launcher", f"Failed to start agent:\n{exc}")
        return False

    # Give the agent a moment to bind the port, then check /health
    time.sleep(2.0)
    ok = is_agent_running()
    if not ok:
        messagebox.showinfo(
            "Allow through Firewall?",
            "If this is the first run, a Windows Firewall prompt may be waiting.\n"
            "Allow access on Private networks, then try Start Agent again.",
        )
    return ok


def open_cli_help() -> None:
    """Open a terminal with `ui.exe --help`."""
    if not UI_EXE.exists():
        messagebox.showerror("UIBridge Launcher", f"CLI not found:\n{UI_EXE}")
        return
    try:
        subprocess.Popen(
            ["cmd", "/k", str(UI_EXE), "--help"],
            cwd=str(UI_EXE.parent),
            creationflags=CREATE_NEW_PROCESS_GROUP,
            shell=False,
        )
    except Exception as exc:
        messagebox.showerror("UIBridge Launcher", f"Failed to open CLI:\n{exc}")


def run_ps_script(script_name: str) -> None:
    """Run a PowerShell helper script from the bundle root (ExecutionPolicy Bypass, no profile)."""
    script = SCRIPTS_DIR / script_name
    if not script.exists():
        messagebox.showerror("UIBridge Launcher", f"Script not found:\n{script}")
        return
    try:
        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            creationflags=CREATE_NEW_PROCESS_GROUP,
            shell=False,
        )
    except Exception as exc:
        messagebox.showerror("UIBridge Launcher", f"Failed to run script:\n{exc}")


def open_logs_folder() -> None:
    """Open the logs directory in Explorer (create it if missing)."""
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(
            ["explorer", str(LOGS_DIR)],
            creationflags=CREATE_NEW_PROCESS_GROUP,
            shell=False,
        )
    except Exception as exc:
        messagebox.showerror("UIBridge Launcher", f"Failed to open logs folder:\n{exc}")


# -----------------------------
# UI
# -----------------------------


class Launcher(tk.Tk):
    """Warm, simple launcher window with live health indicator."""

    def __init__(self) -> None:
        super().__init__()
        self.title("UIBridge Launcher")
        self.geometry("560x360")
        self.resizable(False, False)
        # Cozy colors
        self.configure(bg="#fff8f2")
        self._build_ui()

        # Health polling
        self._running = True
        self._health_lock = threading.Lock()
        self._healthy = False
        threading.Thread(target=self._poll_health_loop, daemon=True).start()
        self.after(400, self._render_health)

    def _build_ui(self) -> None:
        # Title
        title = tk.Label(
            self,
            text="UIBridge CLI",
            font=("Segoe UI", 22, "bold"),
            bg="#fff8f2",
            fg="#2a2320",
        )
        title.pack(pady=(18, 2))

        subtitle = tk.Label(
            self,
            text="Control Windows apps from a friendly CLI.",
            font=("Segoe UI", 11),
            bg="#fff8f2",
            fg="#6b5e57",
        )
        subtitle.pack(pady=(0, 12))

        # Status
        self.status_var = tk.StringVar(value="Agent status: checking…")
        self.status_label = tk.Label(
            self,
            textvariable=self.status_var,
            bg="#fff8f2",
            fg="#2a2320",
            font=("Segoe UI", 10, "bold"),
        )
        self.status_label.pack(pady=(0, 10))

        # Buttons container
        frame = tk.Frame(self, bg="#fff8f2")
        frame.pack(pady=6)

        def btn(parent: tk.Widget, text: str, cmd) -> tk.Button:
            b = tk.Button(
                parent,
                text=text,
                command=cmd,
                relief="groove",
                bd=1,
                bg="#ffe9df",
                activebackground="#ffd9c7",
                fg="#2a2320",
                font=("Segoe UI", 10, "bold"),
                padx=16,
                pady=10,
            )
            return b

        # Row 1
        row1 = tk.Frame(frame, bg="#fff8f2")
        row1.pack(pady=6)
        self.btn_start = btn(row1, "Start Agent", self._on_start_agent)
        self.btn_start.grid(row=0, column=0, padx=6)

        self.btn_cli = btn(row1, "Open CLI", open_cli_help)
        self.btn_cli.grid(row=0, column=1, padx=6)

        self.btn_logs = btn(row1, "Open Logs", open_logs_folder)
        self.btn_logs.grid(row=0, column=2, padx=6)

        # Row 2
        row2 = tk.Frame(frame, bg="#fff8f2")
        row2.pack(pady=6)
        self.btn_cli_shim = btn(
            row2,
            "Install CLI (ui) to PATH",
            lambda: run_ps_script("install_cli_shim.ps1"),
        )
        self.btn_cli_shim.grid(row=0, column=0, padx=6)

        self.btn_enable_startup = btn(
            row2, "Enable Startup", lambda: run_ps_script("install_agent_startup.ps1")
        )
        self.btn_enable_startup.grid(row=0, column=1, padx=6)

        self.btn_disable_startup = btn(
            row2,
            "Disable Startup",
            lambda: run_ps_script("uninstall_agent_startup.ps1"),
        )
        self.btn_disable_startup.grid(row=0, column=2, padx=6)

        # Footer note
        note = tk.Label(
            self,
            text="Tip: First run may show a Windows Firewall prompt. Allow Private network.",
            bg="#fff8f2",
            fg="#6b5e57",
            font=("Segoe UI", 9),
        )
        note.pack(pady=(10, 2))

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- event handlers ----

    def _on_start_agent(self) -> None:
        ok = start_agent_and_check()
        with self._health_lock:
            self._healthy = ok
        self._render_health()

    def _on_close(self) -> None:
        self._running = False
        self.destroy()

    # ---- health polling ----

    def _poll_health_loop(self) -> None:
        # Keep polling even if unhealthy; update shared flag.
        while self._running:
            ok = is_agent_running()
            with self._health_lock:
                self._healthy = ok
            time.sleep(1.2)

    def _render_health(self) -> None:
        with self._health_lock:
            ok = self._healthy

        if ok:
            self.status_var.set("Agent status: ONLINE ✅  (http://127.0.0.1:5025)")
            self.btn_start.configure(state="normal", text="Start Agent")
        else:
            self.status_var.set("Agent status: OFFLINE ⛔  (click Start Agent)")
            self.btn_start.configure(state="normal", text="Start Agent")

        # re-schedule UI refresh
        if self._running:
            self.after(600, self._render_health)


# -----------------------------
# Main entry
# -----------------------------


def main() -> None:
    app = Launcher()
    app.mainloop()


if __name__ == "__main__":
    main()
