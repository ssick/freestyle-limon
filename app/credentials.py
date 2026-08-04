import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv, set_key

from app import state

CREDENTIALS_PATH = Path.home() / "Library" / "Application Support" / "Freestyle Limón" / "credentials.env"

_generation = 0
# The generation fetch_loop last actually attempted a connection for. Stays
# behind _generation until fetch_loop retries with the newly-saved
# credentials - this is what lets connection_status() tell "haven't tried
# the new credentials yet" apart from "tried them and it worked", which a
# bare state.get_error() check can't do (a leftover None from before the
# change looks identical to a fresh success).
_attempted_generation = -1


def load(path: Path = CREDENTIALS_PATH) -> None:
    if path.exists():
        load_dotenv(path, override=True)


def save(email: str, password: Optional[str], path: Path = CREDENTIALS_PATH) -> None:
    global _generation

    path.parent.mkdir(parents=True, exist_ok=True)
    set_key(path, "LIBRE_EMAIL", email)
    os.environ["LIBRE_EMAIL"] = email
    if password:
        set_key(path, "LIBRE_PASSWORD", password)
        os.environ["LIBRE_PASSWORD"] = password

    _generation += 1


def get_generation() -> int:
    return _generation


def mark_attempted(generation: int) -> None:
    global _attempted_generation
    _attempted_generation = generation


def get_attempted_generation() -> int:
    return _attempted_generation


def connection_status() -> dict:
    """Tri-state result of the most recent LibreLinkUp connection attempt.

    'pending' until fetch_loop has actually retried with the currently-saved
    generation - without this, a settings UI checking state.get_error() right
    after a save could see a stale None left over from before the change and
    wrongly report success.
    """
    if _attempted_generation != _generation:
        return {"status": "pending"}
    error = state.get_error()
    if error is None:
        return {"status": "ok"}
    return {"status": "error", "error": error}
