"""
Goal: CDP guard — verify we can import websockets/httpx; not asserting a live debugging session.
"""
import websockets  # noqa: F401
import httpx  # noqa: F401


def test_imports():
    assert True
