"""
UIBridge Agent entrypoint

Goals
- Simple uvicorn runner so packaging/PS scripts can `python -m app.entry` or import run().
- Keep config via env (UIB_HOST/UIB_PORT) and match Agent defaults.
"""

from __future__ import annotations

import os

import uvicorn


def run() -> None:
    host = os.getenv("UIB_HOST", "127.0.0.1")
    port = int(os.getenv("UIB_PORT", "5025"))
    uvicorn.run("app.main:app", host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    run()
