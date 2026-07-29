from dataclasses import dataclass
from typing import Optional


@dataclass
class GlucoseReading:
    value: float
    trend: Optional[str]
    timestamp: Optional[str]
    is_high: bool
    is_low: bool


_latest: Optional[GlucoseReading] = None


def set_latest(reading: GlucoseReading) -> None:
    global _latest
    _latest = reading


def get_latest() -> Optional[GlucoseReading]:
    return _latest
