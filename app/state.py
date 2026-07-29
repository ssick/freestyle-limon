from dataclasses import dataclass
from typing import Optional


@dataclass
class GlucoseReading:
    value: float
    trend: Optional[str]
    timestamp: Optional[str]
    is_high: bool
    is_low: bool


@dataclass
class HistoryPoint:
    value: float
    timestamp: Optional[str]
    is_high: bool
    is_low: bool


_latest: Optional[GlucoseReading] = None
_history: list[HistoryPoint] = []
_target_low: Optional[int] = None
_target_high: Optional[int] = None


def set_latest(reading: GlucoseReading) -> None:
    global _latest
    _latest = reading


def get_latest() -> Optional[GlucoseReading]:
    return _latest


def set_history(history: list[HistoryPoint]) -> None:
    global _history
    _history = history


def get_history() -> list[HistoryPoint]:
    return _history


def set_target_range(target_low: int, target_high: int) -> None:
    global _target_low, _target_high
    _target_low = target_low
    _target_high = target_high


def get_target_range() -> tuple[Optional[int], Optional[int]]:
    return _target_low, _target_high
