"""
Goal: Quick smoke test that CLI entry parses and shows help without crashing.
"""
from typer.testing import CliRunner
from app.cli.cli import app

def test_cli_help():
    r = CliRunner().invoke(app, ["--help"])
    assert r.exit_code == 0
    assert "UI Bridge CLI" in r.stdout
