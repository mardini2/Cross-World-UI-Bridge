"""
Goal: tiny entrypoint so PyInstaller can build ui.exe cleanly.
"""

from app.cli.cli import app

if __name__ == "__main__":
    app()
