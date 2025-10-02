"""
Goal: Manage a single shared API token for the local HTTP agent.
We store it in Windows Credential Manager via `keyring` so it's not sitting in plain text.
"""

import secrets
import time
from typing import Optional

import keyring

_SERVICE = "UIBridgeAgent"
_USERNAME = "X-UIB-Token"
_TIMESTAMP_KEY = "X-UIB-Token-Timestamp"
_TOKEN_LIFETIME = 24 * 60 * 60  # 24 hours in seconds


def _gen_token(n: int = 32) -> str:
    return secrets.token_urlsafe(n)


def _is_token_expired() -> bool:
    """Check if current token is expired."""
    try:
        timestamp_str = keyring.get_password(_SERVICE, _TIMESTAMP_KEY)
        if not timestamp_str:
            return True
        
        timestamp = float(timestamp_str)
        return (time.time() - timestamp) > _TOKEN_LIFETIME
    except (ValueError, TypeError):
        return True


def _validate_token(token: str) -> bool:
    """Validate token format and structure."""
    if not token or not isinstance(token, str):
        return False
    
    # Check token length and format
    if len(token) < 32 or len(token) > 64:
        return False
    
    # Check for valid base64url characters
    import string
    valid_chars = string.ascii_letters + string.digits + '-_'
    return all(c in valid_chars for c in token)


def get_or_create_token() -> str:
    current = keyring.get_password(_SERVICE, _USERNAME)
    
    # Check if token exists, is valid, and not expired
    if current and _validate_token(current) and not _is_token_expired():
        return current
    
    # Generate new token
    newv = _gen_token()
    keyring.set_password(_SERVICE, _USERNAME, newv)
    keyring.set_password(_SERVICE, _TIMESTAMP_KEY, str(time.time()))
    return newv


def get_token() -> Optional[str]:
    token = keyring.get_password(_SERVICE, _USERNAME)
    if token and _validate_token(token) and not _is_token_expired():
        return token
    return None


def set_token(value: str) -> None:
    if not _validate_token(value):
        raise ValueError("Invalid token format")
    keyring.set_password(_SERVICE, _USERNAME, value)
    keyring.set_password(_SERVICE, _TIMESTAMP_KEY, str(time.time()))


def reset_token() -> str:
    newv = _gen_token()
    keyring.set_password(_SERVICE, _USERNAME, newv)
    keyring.set_password(_SERVICE, _TIMESTAMP_KEY, str(time.time()))
    return newv
