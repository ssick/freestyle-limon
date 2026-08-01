import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import state
from app.libre_client import build_client, fetch_reading_and_history

# When frozen into a standalone executable, __file__ resolves inside the
# PyInstaller temp extraction dir, not next to the binary the user launched -
# so .env has to be looked up relative to sys.executable in that case instead.
# Inside a .app bundle, sys.executable lives at Foo.app/Contents/MacOS/foo, so
# walk up to the folder containing Foo.app, where a user would naturally drop .env.
if getattr(sys, "frozen", False):
    exe_path = Path(sys.executable).resolve()
    macos_dir = exe_path.parent
    bundle_dir = macos_dir.parent.parent
    if macos_dir.name == "MacOS" and macos_dir.parent.name == "Contents" and bundle_dir.suffix == ".app":
        APP_DIR = bundle_dir.parent
    else:
        APP_DIR = macos_dir
else:
    APP_DIR = Path(__file__).resolve().parent.parent

load_dotenv(APP_DIR / ".env")

logger = logging.getLogger("freestyle_limon")

FETCH_INTERVAL_SECONDS = 60
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def is_stale_reading(current_timestamp: Optional[str], previous_timestamp: Optional[str]) -> bool:
    """A reading is stale if LibreLinkUp served the same timestamp as last poll.

    The sensor produces a new value once a minute and we poll once a minute
    (FETCH_INTERVAL_SECONDS), so an unchanged timestamp means nothing new
    arrived - not that the poll itself failed (that's handled by set_error).
    """
    return current_timestamp is not None and current_timestamp == previous_timestamp


async def fetch_loop() -> None:
    client = None
    patient = None
    while True:
        try:
            if client is None:
                client, patient = await asyncio.to_thread(build_client)
            previous_reading = state.get_latest()
            reading, history, target_low, target_high = await asyncio.to_thread(
                fetch_reading_and_history, client, patient
            )
            state.set_latest(reading)
            state.set_history(history)
            state.set_target_range(target_low, target_high)
            state.set_is_stale(
                is_stale_reading(
                    reading.timestamp,
                    previous_reading.timestamp if previous_reading else None,
                )
            )
            state.set_error(None)
            logger.info("Fetched glucose reading: %s", reading)
        except Exception as exc:
            logger.exception("Failed to fetch glucose reading")
            state.set_error(str(exc))
        await asyncio.sleep(FETCH_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(fetch_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/latest")
async def get_latest():
    reading = state.get_latest()
    if reading is None:
        return {"status": "pending", "error": state.get_error()}
    target_low, target_high = state.get_target_range()
    return {
        "status": "ok",
        "value": reading.value,
        "trend": reading.trend,
        "timestamp": reading.timestamp,
        "is_high": reading.is_high,
        "is_low": reading.is_low,
        "target_low": target_low,
        "target_high": target_high,
        "stale": state.get_is_stale(),
        "history": [
            {
                "value": point.value,
                "timestamp": point.timestamp,
                "is_high": point.is_high,
                "is_low": point.is_low,
            }
            for point in state.get_history()
        ],
    }


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")
