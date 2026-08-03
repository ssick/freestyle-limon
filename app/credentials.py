import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv, set_key

CREDENTIALS_PATH = Path.home() / "Library" / "Application Support" / "Freestyle Limón" / "credentials.env"

_generation = 0


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
