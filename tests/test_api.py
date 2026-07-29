from fastapi.testclient import TestClient

from app import state
from app.main import app
from app.state import GlucoseReading, HistoryPoint


def test_latest_pending_when_no_reading(monkeypatch):
    monkeypatch.setattr(state, "_latest", None)
    monkeypatch.setattr(state, "_error", None)

    with TestClient(app) as client:
        response = client.get("/api/latest")

    assert response.status_code == 200
    assert response.json() == {"status": "pending", "error": None}


def test_latest_pending_surfaces_fetch_error(monkeypatch):
    monkeypatch.setattr(state, "_latest", None)
    monkeypatch.setattr(state, "_error", "Missing LIBRE_EMAIL / LIBRE_PASSWORD - check your .env file")

    with TestClient(app) as client:
        response = client.get("/api/latest")

    assert response.status_code == 200
    assert response.json() == {
        "status": "pending",
        "error": "Missing LIBRE_EMAIL / LIBRE_PASSWORD - check your .env file",
    }


def test_latest_returns_seeded_reading(monkeypatch):
    monkeypatch.setattr(
        state,
        "_latest",
        GlucoseReading(
            value=100.0,
            trend="→",
            timestamp="2026-07-29T12:00:00",
            is_high=False,
            is_low=False,
        ),
    )
    monkeypatch.setattr(
        state,
        "_history",
        [
            HistoryPoint(value=95.0, timestamp="2026-07-29T11:45:00", is_high=False, is_low=False),
            HistoryPoint(value=100.0, timestamp="2026-07-29T12:00:00", is_high=False, is_low=False),
        ],
    )
    monkeypatch.setattr(state, "_target_low", 70)
    monkeypatch.setattr(state, "_target_high", 180)

    with TestClient(app) as client:
        response = client.get("/api/latest")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "value": 100.0,
        "trend": "→",
        "timestamp": "2026-07-29T12:00:00",
        "is_high": False,
        "is_low": False,
        "target_low": 70,
        "target_high": 180,
        "history": [
            {"value": 95.0, "timestamp": "2026-07-29T11:45:00", "is_high": False, "is_low": False},
            {"value": 100.0, "timestamp": "2026-07-29T12:00:00", "is_high": False, "is_low": False},
        ],
    }


def test_favicon_served_from_static():
    with TestClient(app) as client:
        response = client.get("/static/favicon.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_widget_page_served_from_static():
    with TestClient(app) as client:
        response = client.get("/static/widget.html")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"


def test_lcd_font_served_from_static():
    with TestClient(app) as client:
        response = client.get("/static/fonts/DSEG7Classic-Bold.woff2")

    assert response.status_code == 200
    assert response.headers["content-type"] == "font/woff2"
