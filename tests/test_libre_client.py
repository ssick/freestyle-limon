from types import SimpleNamespace

from app.libre_client import fetch_latest_reading


class FakeClient:
    def __init__(self, measurement):
        self._measurement = measurement

    def latest(self, patient_identifier):
        return self._measurement


def test_fetch_latest_reading_normalizes_measurement():
    measurement = SimpleNamespace(
        value=105.0,
        trend=SimpleNamespace(indicator="→"),
        timestamp=SimpleNamespace(isoformat=lambda: "2026-07-29T12:00:00"),
    )

    reading = fetch_latest_reading(FakeClient(measurement), patient="patient-1")

    assert reading.value == 105.0
    assert reading.trend == "→"
    assert reading.timestamp == "2026-07-29T12:00:00"


def test_fetch_latest_reading_handles_missing_trend_and_timestamp():
    measurement = SimpleNamespace(value=90.0, trend=None, timestamp=None)

    reading = fetch_latest_reading(FakeClient(measurement), patient="patient-1")

    assert reading.value == 90.0
    assert reading.trend is None
    assert reading.timestamp is None
