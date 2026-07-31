from typing import Optional


def badge_text(value: Optional[float], error: Optional[str]) -> Optional[str]:
    if error is not None:
        return None
    if value is None:
        return None
    return str(round(value))
