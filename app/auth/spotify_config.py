"""
Goal: Store and retrieve the Spotify Client ID per-user in Windows Credential Manager.
So the project works for anyone without hard-coding IDs in the repo.
"""

from typing import Optional

import keyring

# One service bucket for all Spotify-related secrets for this app
_SERVICE = "UIBridgeSpotify"

# We already use "access_token"/"refresh_token" elsewhere; "client_id" joins them here.
_K_CLIENT_ID = "client_id"


def set_client_id(value: str) -> None:
    """
    Save the Spotify Client ID in Windows Credential Manager.
    """
    if not value or not isinstance(value, str):
        raise ValueError("Client ID must be a non-empty string.")
    keyring.set_password(_SERVICE, _K_CLIENT_ID, value)


def get_client_id() -> Optional[str]:
    """
    Read the Spotify Client ID if previously saved.
    """
    return keyring.get_password(_SERVICE, _K_CLIENT_ID)


def clear_client_id() -> None:
    """
    Remove the saved Spotify Client ID.
    """
    # keyring doesn't have a direct delete API across all backends,
    # so overwrite with empty string to effectively clear it.
    keyring.set_password(_SERVICE, _K_CLIENT_ID, "")
