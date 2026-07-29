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
