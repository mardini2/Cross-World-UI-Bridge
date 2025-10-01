"""
Goal: Wrapper for Spotify adapter so the API layer stays thin.
"""

from app.adapters import spotify


async def now() -> dict:
    return await spotify.now_playing()


async def play(query: str) -> bool:
    return await spotify.play_query(query)


async def pause() -> bool:
    return await spotify.pause()


async def devices() -> list[dict]:
    return await spotify.list_devices()
