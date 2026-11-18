import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

SECRET = "s" * 40


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(settings, "moodle_sso_secret", SECRET)
    monkeypatch.setattr(settings, "moodle_url", "https://lms.example")
    return TestClient(app)


def _token(**over):
    now = int(time.time())
    claims = {"iss": "https://lms.example", "aud": "clo-search", "sub": "22130001", "courseid": 50, "iat": now, "exp": now + 60}
    claims.update(over)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def test_search_rejects_bad_signature(client):
    r = client.get("/api/lms/materials/search", params={"token": _token() + "x", "q": "khoa"})
    assert r.status_code == 401


def test_search_rejects_expired(client):
    r = client.get("/api/lms/materials/search", params={"token": _token(exp=int(time.time()) - 600), "q": "khoa"})
    assert r.status_code == 401


def test_search_rejects_wrong_issuer_and_audience(client):
    assert client.get("/api/lms/materials/search", params={"token": _token(iss="https://evil"), "q": "khoa"}).status_code == 401
    assert client.get("/api/lms/materials/search", params={"token": _token(aud="clo-analytics"), "q": "khoa"}).status_code == 401


def test_search_returns_list_for_valid_token(client):
    r = client.get("/api/lms/materials/search", params={"token": _token(courseid=999999), "q": "khoa"})
    assert r.status_code == 200 and r.json() == []
