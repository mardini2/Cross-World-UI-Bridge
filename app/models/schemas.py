"""
Goal: Pydantic models for request/response shapes across the API.
We keep them boring on purpose so they're stable contracts.
"""
from pydantic import BaseModel, AnyHttpUrl
from typing import Optional, List

class HealthResponse(BaseModel):
    status: str
    name: str
    version: str
    time_utc: str
    port: int

class ErrorResponse(BaseModel):
    error: str
    message: str
    detail: Optional[str] = None

class PingResponse(BaseModel):
    pong: str
    token_last4: str

class BrowserOpenRequest(BaseModel):
    url: AnyHttpUrl

class BrowserOpenResponse(BaseModel):
    ok: bool
    message: str
    url: str

class SpotifyPlayRequest(BaseModel):
    query: str

class SpotifyNowResponse(BaseModel):
    artist: Optional[str] = None
    track: Optional[str] = None
    is_playing: bool = False

class WordCountResponse(BaseModel):
    path: Optional[str] = None
    words: int

class WindowListItem(BaseModel):
    title: str

class WindowListResponse(BaseModel):
    windows: List[WindowListItem] = []

class FocusRequest(BaseModel):
    title_substring: str
    strict: bool = False
