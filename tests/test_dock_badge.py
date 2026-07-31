from app.dock_badge import badge_text


def test_badge_text_none_when_no_reading_yet():
    assert badge_text(None, None) is None


def test_badge_text_none_when_error_even_with_cached_value():
    assert badge_text(105.0, "some error") is None


def test_badge_text_normal_case():
    assert badge_text(105.0, None) == "105"


def test_badge_text_rounds_to_nearest_int():
    assert badge_text(99.6, None) == "100"
