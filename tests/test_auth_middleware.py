"""
Goal: Prove that /health is open and /v1/ping requires the header.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_open():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"

def test_ping_requires_header():
    r = client.get("/v1/ping")
    assert r.status_code == 401
