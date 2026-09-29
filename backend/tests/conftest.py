"""Kiểm thử tích hợp chạy trên MySQL thật: dựng lại CSDL + dữ liệu minh họa trước phiên kiểm thử."""
import contextlib, io, os

# kiểm thử dùng CSDL Moodle MÔ PHỎNG riêng, không đụng tới Moodle thật (nếu có)
os.environ["MOODLE_DB_NAME"] = "moodle_sim"

import pytest
from fastapi.testclient import TestClient

from app import cli
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def fresh_database():
    with contextlib.redirect_stdout(io.StringIO()):
        cli.init_db(); cli.seed_demo(); cli.simulate_paper(); cli.simulate_moodle()
    yield


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


def _login(client, u, p):
    r = client.post("/api/auth/login", json={"username": u, "password": p})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture(scope="session")
def gv(client):
    return _login(client, "gv.son", "Gv@123456")


@pytest.fixture(scope="session")
def gv_other(client):
    return _login(client, "gv.binh", "Gv@123456")


@pytest.fixture(scope="session")
def admin(client):
    return _login(client, "admin", "Admin@123")
