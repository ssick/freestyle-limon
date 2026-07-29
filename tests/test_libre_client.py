from types import SimpleNamespace

from app.libre_client import fetch_reading_and_history


class FakeClient:
    def __init__(self, current, history, target_low=70, target_high=180):
        self._current = current
        self._history = history
        self._target_low = target_low
        self._target_high = target_high

    def read(self, patient_identifier):
        connection = SimpleNamespace(target_low=self._target_low, target_high=self._target_high)
        data = SimpleNamespace(connection=connection)
        return SimpleNamespace(current=self._current, history=self._history, data=data)


def test_fetch_reading_and_history_normalizes_measurement():
    current = SimpleNamespace(
        value=105.0,
        trend=SimpleNamespace(indicator="→"),
        timestamp=SimpleNamespace(isoformat=lambda: "2026-07-29T12:00:00"),
        is_high=False,
        is_low=False,
    )

    reading, history = fetch_reading_and_history(FakeClient(current, []), patient="patient-1")

    assert reading.value == 105.0
    assert reading.trend == "→"
    assert reading.timestamp == "2026-07-29T12:00:00"
    assert reading.is_high is False
    assert reading.is_low is False
    assert history == []


def test_fetch_reading_and_history_handles_missing_trend_and_timestamp():
    current = SimpleNamespace(value=90.0, trend=None, timestamp=None, is_high=False, is_low=False)

    reading, history = fetch_reading_and_history(FakeClient(current, []), patient="patient-1")

    assert reading.value == 90.0
    assert reading.trend is None
    assert reading.timestamp is None


def test_fetch_reading_and_history_passes_through_is_high():
    current = SimpleNamespace(value=220.0, trend=None, timestamp=None, is_high=True, is_low=False)

    reading, history = fetch_reading_and_history(FakeClient(current, []), patient="patient-1")

    assert reading.is_high is True
    assert reading.is_low is False


def test_fetch_reading_and_history_passes_through_is_low():
    current = SimpleNamespace(value=60.0, trend=None, timestamp=None, is_high=False, is_low=True)

    reading, history = fetch_reading_and_history(FakeClient(current, []), patient="patient-1")

    assert reading.is_high is False
    assert reading.is_low is True


def test_fetch_reading_and_history_normalizes_history_points():
    current = SimpleNamespace(value=100.0, trend=None, timestamp=None, is_high=False, is_low=False)
    history_points = [
        SimpleNamespace(
            value=95.0,
            timestamp=SimpleNamespace(isoformat=lambda: "2026-07-29T11:00:00"),
            is_high=False,
            is_low=False,
        ),
        SimpleNamespace(
            value=210.0,
            timestamp=SimpleNamespace(isoformat=lambda: "2026-07-29T11:15:00"),
            is_high=False,
            is_low=False,
        ),
    ]

    _, history = fetch_reading_and_history(
        FakeClient(current, history_points, target_low=70, target_high=180), patient="patient-1"
    )

    assert len(history) == 2
    assert history[0].value == 95.0
    assert history[0].timestamp == "2026-07-29T11:00:00"
    assert history[0].is_high is False
    assert history[1].value == 210.0
    assert history[1].is_high is True


def test_fetch_reading_and_history_derives_range_status_from_target_range():
    """LibreLinkUp never sets isHigh/isLow on historical points, so status must
    come from comparing the value against the patient's target range - not from
    trusting the (always-False) flag on each point."""
    current = SimpleNamespace(value=100.0, trend=None, timestamp=None, is_high=False, is_low=False)
    history_points = [
        SimpleNamespace(value=55.0, timestamp=None, is_high=False, is_low=False),
        SimpleNamespace(value=100.0, timestamp=None, is_high=False, is_low=False),
        SimpleNamespace(value=200.0, timestamp=None, is_high=False, is_low=False),
    ]

    _, history = fetch_reading_and_history(
        FakeClient(current, history_points, target_low=70, target_high=180), patient="patient-1"
    )

    assert history[0].is_low is True and history[0].is_high is False
    assert history[1].is_low is False and history[1].is_high is False
    assert history[2].is_high is True and history[2].is_low is False
