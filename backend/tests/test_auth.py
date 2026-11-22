import base64
import secrets

import pytest

from app import create_app
from app.config import Config
from app.models.project import ProjectManager
from app.utils import auth as auth_utils


# Every credential and token in this file is generated at run time.
PROTECTED = "/api/graph/project/list"


def _random():
    return secrets.token_urlsafe(16)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(tmp_path))
    monkeypatch.setattr(auth_utils, "FAILED_LOGIN_DELAY_SECONDS", 0)
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


@pytest.fixture
def credentials(monkeypatch):
    """Turn login on with random credentials for one test."""
    username, password = _random(), _random()
    monkeypatch.setattr(Config, "AUTH_USERNAME", username)
    monkeypatch.setattr(Config, "AUTH_PASSWORD", password)
    return username, password


@pytest.fixture
def login_off(monkeypatch):
    monkeypatch.setattr(Config, "AUTH_USERNAME", None)
    monkeypatch.setattr(Config, "AUTH_PASSWORD", None)


def _login(client, username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_everything_stays_open_without_auth_settings(client, login_off):
    assert client.get(PROTECTED).status_code == 200
    assert client.get("/api/auth/status").json["data"] == {
        "enabled": False,
        "authenticated": True,
    }


def test_login_endpoint_does_nothing_without_auth_settings(client, login_off):
    response = _login(client, _random(), _random())

    assert response.status_code == 200
    assert response.json["data"] == {"enabled": False, "token": None}


def test_api_requires_a_token_when_auth_settings_are_present(client, credentials):
    response = client.get(PROTECTED)

    assert response.status_code == 401
    assert response.json["code"] == "auth_required"
    assert client.get("/api/auth/status").json["data"] == {
        "enabled": True,
        "authenticated": False,
    }


def test_health_and_preflight_stay_reachable(client, credentials):
    assert client.get("/health").status_code == 200
    assert client.options(PROTECTED).status_code != 401


def test_the_configured_credentials_unlock_the_api(client, credentials):
    response = _login(client, *credentials)

    assert response.status_code == 200
    token = response.json["data"]["token"]
    assert client.get(PROTECTED, headers=_bearer(token)).status_code == 200
    assert client.get("/api/auth/status", headers=_bearer(token)).json["data"] == {
        "enabled": True,
        "authenticated": True,
    }


@pytest.mark.parametrize(
    "case",
    ["wrong password", "wrong username", "empty strings", "missing fields", "not strings"],
)
def test_wrong_credentials_are_rejected(client, credentials, case):
    username, password = credentials
    sent = {
        "wrong password": (username, _random()),
        "wrong username": (_random(), password),
        "empty strings": ("", ""),
        "missing fields": (None, None),
        "not strings": ([username], {"value": password}),
    }[case]

    response = _login(client, *sent)

    assert response.status_code == 401
    assert response.json["success"] is False
    assert response.json.get("code") is None  # not a "session expired" response


@pytest.mark.parametrize("scheme", ["random bearer", "basic", "bearer without token", "empty"])
def test_invalid_authorization_headers_are_rejected(client, credentials, scheme):
    username, password = credentials
    header = {
        "random bearer": f"Bearer {_random()}",
        "basic": "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode(),
        "bearer without token": "Bearer",
        "empty": "",
    }[scheme]

    assert client.get(PROTECTED, headers={"Authorization": header}).status_code == 401


def test_tampered_token_is_rejected(client, credentials):
    token = _login(client, *credentials).json["data"]["token"]
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")

    assert client.get(PROTECTED, headers=_bearer(tampered)).status_code == 401


def test_changing_the_password_signs_existing_sessions_out(client, credentials, monkeypatch):
    token = _login(client, *credentials).json["data"]["token"]
    monkeypatch.setattr(Config, "AUTH_PASSWORD", _random())

    assert client.get(PROTECTED, headers=_bearer(token)).status_code == 401


def test_expired_token_is_rejected(client, credentials, monkeypatch):
    token = _login(client, *credentials).json["data"]["token"]
    monkeypatch.setattr(auth_utils, "TOKEN_MAX_AGE_SECONDS", -1)

    assert client.get(PROTECTED, headers=_bearer(token)).status_code == 401


@pytest.mark.parametrize(
    ("username_set", "password_set", "has_error"),
    [(True, False, True), (False, True, True), (True, True, False), (False, False, False)],
)
def test_auth_settings_must_be_set_together(monkeypatch, username_set, password_set, has_error):
    monkeypatch.setattr(Config, "LLM_API_KEY", _random())
    monkeypatch.setattr(Config, "ZEP_API_KEY", _random())
    monkeypatch.setattr(Config, "AUTH_USERNAME", _random() if username_set else None)
    monkeypatch.setattr(Config, "AUTH_PASSWORD", _random() if password_set else None)

    errors = Config.validate()

    assert any("AUTH_USERNAME" in error for error in errors) is has_error
