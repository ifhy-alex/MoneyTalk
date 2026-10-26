from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from moneytalk.config import get_settings


@pytest.fixture
def desktop_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<!doctype html><title>MoneyTalk</title>", encoding="utf-8")
    (web / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (web / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    monkeypatch.setenv("STATIC_DIR", str(web))
    monkeypatch.setenv("DESKTOP_MODE", "1")
    monkeypatch.setenv("INBOX_DIR", str(tmp_path / "inbox"))
    get_settings.cache_clear()
    from moneytalk.main import create_app

    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def test_spa_routes_fall_back_to_index(desktop_client: TestClient) -> None:
    for path in ("/", "/ingesta", "/mercado/AAPL"):
        resp = desktop_client.get(path)
        assert resp.status_code == 200
        assert "<title>MoneyTalk</title>" in resp.text
    assert desktop_client.get("/assets/app.js").text == "console.log(1)"
    assert desktop_client.get("/favicon.svg").text == "<svg/>"


def test_spa_does_not_swallow_api_or_escape_root(desktop_client: TestClient) -> None:
    assert desktop_client.get("/api/no-existe").status_code == 404
    # Una ruta con .. no puede leer archivos fuera de la carpeta del frontend.
    resp = desktop_client.get("/..%2F..%2Fpyproject.toml")
    assert "<title>MoneyTalk</title>" in resp.text


def test_inbox_reports_real_path(desktop_client: TestClient, tmp_path: Path) -> None:
    body = desktop_client.get("/api/ingestion/inbox").json()
    assert Path(body["path"]) == (tmp_path / "inbox").resolve()


def test_index_is_not_cached(desktop_client: TestClient) -> None:
    # Tras actualizar la app, un index.html cacheado apuntaría a assets que ya no existen.
    assert desktop_client.get("/inicio").headers["cache-control"] == "no-cache"


def test_rejects_cross_site_requests(desktop_client: TestClient) -> None:
    cross = {"sec-fetch-site": "cross-site", "sec-fetch-mode": "no-cors"}
    assert desktop_client.post("/api/ingestion/inbox/open", headers=cross).status_code == 403
    assert (
        desktop_client.get("/api/gmail/connect?origin=http://localhost", headers=cross).status_code
        == 403
    )
    same = {"sec-fetch-site": "same-origin", "sec-fetch-mode": "cors"}
    assert desktop_client.get("/api/ingestion/inbox", headers=same).status_code == 200


def test_google_can_navigate_back_to_the_callback(desktop_client: TestClient) -> None:
    nav = {"sec-fetch-site": "cross-site", "sec-fetch-mode": "navigate"}
    # Sin flujo pendiente responde 400, pero el filtro de otro sitio la deja pasar.
    assert desktop_client.get("/api/gmail/callback?state=x", headers=nav).status_code == 400
