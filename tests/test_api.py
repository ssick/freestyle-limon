from fastapi.testclient import TestClient

from app import state
from app.main import app
from app.state import GlucoseReading, HistoryPoint


def test_latest_pending_when_no_reading(monkeypatch):
    monkeypatch.setattr(state, "_latest", None)

    with TestClient(app) as client:
        response = client.get("/api/latest")

    assert response.status_code == 200
    assert response.json() == {"status": "pending"}


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
