from app.main import is_stale_reading


def test_stale_when_current_matches_previous():
    assert is_stale_reading("2026-07-29T12:00:00", "2026-07-29T12:00:00") is True


def test_not_stale_when_current_differs_from_previous():
    assert is_stale_reading("2026-07-29T12:01:00", "2026-07-29T12:00:00") is False


def test_not_stale_when_both_timestamps_none():
    assert is_stale_reading(None, None) is False


def test_not_stale_when_current_is_none():
    assert is_stale_reading(None, "2026-07-29T12:00:00") is False


def test_not_stale_on_first_poll_with_no_previous_reading():
    assert is_stale_reading("2026-07-29T12:00:00", None) is False
