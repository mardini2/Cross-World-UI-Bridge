"""
Goal: Centralized configuration for the app (paths, ports, feature flags).
Comments aim to be friendly and clear rather than formal.
"""

import os
from pathlib import Path

# Grab the local appdata folder in a Windows-friendly way
LOCAL_APPDATA = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
APP_DIR = Path(LOCAL_APPDATA) / "UIBridge"
LOG_DIR = APP_DIR / "logs"
DB_PATH = APP_DIR / "state.db"

# Port for the local API; safe default that won't collide with common apps
UIB_PORT = int(os.getenv("UIB_PORT", "5025"))
UIB_HOST = os.getenv("UIB_HOST", "127.0.0.1")

# Feature flags to keep "spicy" things under your control
ALLOW_INPUT_INJECTION = (
    os.getenv("UIB_ALLOW_INPUT_INJECTION", "false").lower() == "true"
)
ENABLE_TELEMETRY = os.getenv("UIB_ENABLE_TELEMETRY", "false").lower() == "true"

# Spotify OAuth (you must set SPOTIFY_CLIENT_ID in your env; secret is not needed for PKCE)
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_REDIRECT = f"http://{UIB_HOST}:{UIB_PORT}/auth/spotify/callback"

# CDP: default debugging port
CDP_PORT = int(os.getenv("UIB_CDP_PORT", "9222"))

# Make sure folders exist
APP_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
