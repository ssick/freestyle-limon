import asyncio

from app import credentials
from app.main import _sleep_until_next_fetch, is_stale_reading


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


def test_sleep_until_next_fetch_returns_early_on_generation_change(monkeypatch):
    monkeypatch.setattr(credentials, "_generation", 1)

    async def run():
        async def bump_generation_shortly():
            await asyncio.sleep(0.02)
            monkeypatch.setattr(credentials, "_generation", 2)

        bump_task = asyncio.create_task(bump_generation_shortly())
        start = asyncio.get_event_loop().time()
        await _sleep_until_next_fetch(1, total_seconds=5, poll_interval=0.01)
        elapsed = asyncio.get_event_loop().time() - start
        await bump_task
        assert elapsed < 1

    asyncio.run(run())


def test_sleep_until_next_fetch_waits_full_duration_when_no_change(monkeypatch):
    monkeypatch.setattr(credentials, "_generation", 1)

    async def run():
        start = asyncio.get_event_loop().time()
        await _sleep_until_next_fetch(1, total_seconds=0.05, poll_interval=0.01)
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 0.04

    asyncio.run(run())
