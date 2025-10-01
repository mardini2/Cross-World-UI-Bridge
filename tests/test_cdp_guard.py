"""
Goal: CDP guard — verify we can import websockets/httpx; not asserting a live Edge debugging session here.
"""
def test_imports():
    import websockets, httpx  # noqa: F401
