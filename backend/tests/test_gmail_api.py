import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from moneytalk.api import gmail as gmail_api
from moneytalk.config import Settings

SECRETS = {
    "installed": {
        "client_id": "x.apps.googleusercontent.com",
        "client_secret": "s",
        "redirect_uris": ["http://localhost"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    s = Settings(
        gmail_credentials_file=tmp_path / "cred.json",
        gmail_token_file=tmp_path / "token.json",
        gmail_label="",
    )
    monkeypatch.setattr(gmail_api, "get_settings", lambda: s)
    return s


def test_status_lists_cr_banks(client: TestClient, settings: Settings) -> None:
    body = client.get("/api/gmail/status").json()
    assert body["connected"] is False and body["has_credentials"] is False
    assert any(b["name"] == "Banco Popular" for b in body["banks"])
    assert "Costa Rica" in body["mode"]


def test_upload_credentials_validates(client: TestClient, settings: Settings) -> None:
    bad = client.post(
        "/api/gmail/credentials", files={"file": ("c.json", b"{}", "application/json")}
    )
    assert bad.status_code == 422
    ok = client.post(
        "/api/gmail/credentials",
        files={"file": ("c.json", json.dumps(SECRETS).encode(), "application/json")},
    )
    assert ok.status_code == 204 and settings.gmail_credentials_file.exists()


def test_connect_and_callback(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.gmail_credentials_file.write_text(json.dumps(SECRETS))
    assert (
        client.get("/api/gmail/connect", params={"origin": "https://evil.com"}).status_code == 422
    )

    res = client.get("/api/gmail/connect", params={"origin": "http://localhost:5173"}).json()
    assert res["auth_url"].startswith("https://accounts.google.com/")
    assert "code_challenge=" in res["auth_url"]  # PKCE
    assert "gmail.readonly" in res["auth_url"]
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A5173%2Fapi%2Fgmail%2Fcallback" in res["auth_url"]
    state = next(iter(gmail_api._PENDING))

    saved: list[str] = []

    def fake_finish(flow: Any, code: str, token_file: Path) -> None:
        saved.append(code)
        token_file.write_text("{}")

    monkeypatch.setattr(gmail_api, "finish_web_flow", fake_finish)
    cb = client.get(
        "/api/gmail/callback", params={"state": state, "code": "abc"}, follow_redirects=False
    )
    assert cb.status_code == 307
    assert cb.headers["location"] == "http://localhost:5173/ingesta?gmail=conectado"
    assert saved == ["abc"]
    # el mismo state no se puede reutilizar
    again = client.get(
        "/api/gmail/callback", params={"state": state, "code": "abc"}, follow_redirects=False
    )
    assert again.status_code == 400

    client.post("/api/gmail/disconnect")
    assert not settings.gmail_token_file.exists()
