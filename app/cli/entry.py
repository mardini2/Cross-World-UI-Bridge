"""
Goal: Entry point that exposes the Typer CLI as a standard script.
So we can build ui.exe with PyInstaller and users just run 'ui'.
"""

from app.cli.cli import app

if __name__ == "__main__":
    app()
