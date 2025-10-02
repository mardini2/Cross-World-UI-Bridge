"""
Goal: Centralized configuration for the app (paths, ports, feature flags).
Comments aim to be friendly and clear rather than formal.
"""

import os
import re
from pathlib import Path


def _validate_port(port_str: str, default: int) -> int:
    """Validate port number is in valid range."""
    try:
        port = int(port_str)
        if 1024 <= port <= 65535:
            return port
    except ValueError:
        pass
    return default


def _validate_host(host_str: str, default: str) -> str:
    """Validate host is localhost or valid IP."""
    if not host_str:
        return default
    
    # Only allow localhost variants and private IPs
    allowed_hosts = {'127.0.0.1', 'localhost', '::1'}
    if host_str in allowed_hosts:
        return host_str
    
    # Validate private IP ranges
    if re.match(r'^192\.168\.\d{1,3}\.\d{1,3}$', host_str) or \
       re.match(r'^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$', host_str) or \
       re.match(r'^172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}$', host_str):
        return host_str
    
    return default


# Grab the local appdata folder in a Windows-friendly way
LOCAL_APPDATA = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
APP_DIR = Path(LOCAL_APPDATA) / "UIBridge"
LOG_DIR = APP_DIR / "logs"
DB_PATH = APP_DIR / "state.db"

# Port for the local API; safe default that won't collide with common apps
UIB_PORT = _validate_port(os.getenv("UIB_PORT", "5025"), 5025)
UIB_HOST = _validate_host(os.getenv("UIB_HOST", "127.0.0.1"), "127.0.0.1")

# Feature flags to keep "spicy" things under your control
ALLOW_INPUT_INJECTION = (
    os.getenv("UIB_ALLOW_INPUT_INJECTION", "false").lower() == "true"
)
ENABLE_TELEMETRY = os.getenv("UIB_ENABLE_TELEMETRY", "false").lower() == "true"

# Spotify OAuth (you must set SPOTIFY_CLIENT_ID in your env; secret is not needed for PKCE)
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_REDIRECT = f"http://{UIB_HOST}:{UIB_PORT}/auth/spotify/callback"

# CDP: default debugging port
CDP_PORT = _validate_port(os.getenv("UIB_CDP_PORT", "9222"), 9222)

# Make sure folders exist
APP_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
