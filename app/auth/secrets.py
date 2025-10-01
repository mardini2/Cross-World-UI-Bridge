"""
Goal: Manage a single shared API token for the local HTTP agent.
We store it in Windows Credential Manager via `keyring` so it's not sitting in plain text.
"""
import secrets
import keyring
from typing import Optional

_SERVICE = "UIBridgeAgent"
_USERNAME = "X-UIB-Token"

def _gen_token(n: int = 32) -> str:
    return secrets.token_urlsafe(n)

def get_or_create_token() -> str:
    current = keyring.get_password(_SERVICE, _USERNAME)
    if current:
        return current
    newv = _gen_token()
    keyring.set_password(_SERVICE, _USERNAME, newv)
    return newv

def get_token() -> Optional[str]:
    return keyring.get_password(_SERVICE, _USERNAME)

def set_token(value: str) -> None:
    keyring.set_password(_SERVICE, _USERNAME, value)

def reset_token() -> str:
    newv = _gen_token()
    keyring.set_password(_SERVICE, _USERNAME, newv)
    return newv
