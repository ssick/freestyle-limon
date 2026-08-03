import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app import broadcast, credentials, state
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

credentials.load()
load_dotenv(APP_DIR / ".env")

logger = logging.getLogger("freestyle_limon")

FETCH_INTERVAL_SECONDS = 60
CREDENTIAL_POLL_INTERVAL_SECONDS = 1
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def is_stale_reading(current_timestamp: Optional[str], previous_timestamp: Optional[str]) -> bool:
    """A reading is stale if LibreLinkUp served the same timestamp as last poll.

    The sensor produces a new value once a minute and we poll once a minute
    (FETCH_INTERVAL_SECONDS), so an unchanged timestamp means nothing new
    arrived - not that the poll itself failed (that's handled by set_error).
    """
    return current_timestamp is not None and current_timestamp == previous_timestamp


async def _sleep_until_next_fetch(
    generation: int,
    total_seconds: float = FETCH_INTERVAL_SECONDS,
    poll_interval: float = CREDENTIAL_POLL_INTERVAL_SECONDS,
) -> None:
    """Sleep for total_seconds, but wake early if credentials changed.

    Without this, saving new credentials in Settings wouldn't be retried
    until the current 60s sleep happened to finish - so a Settings page
    polling for a result for only ~20s could time out even for a correct
    password, let alone catch a wrong one in time to report it.
    """
    elapsed = 0.0
    while elapsed < total_seconds:
        if credentials.get_generation() != generation:
            return
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval


async def fetch_loop() -> None:
    client = None
    patient = None
    last_seen_generation = credentials.get_generation()
    while True:
        try:
            if credentials.get_generation() != last_seen_generation:
                client = None
                patient = None
                last_seen_generation = credentials.get_generation()
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
        credentials.mark_attempted(last_seen_generation)
        await broadcast.publish(_build_latest_payload())
        await _sleep_until_next_fetch(last_seen_generation)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(fetch_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _build_latest_payload() -> dict:
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


@app.get("/api/latest")
async def get_latest():
    return _build_latest_payload()


@app.get("/api/stream")
async def stream():
    async def event_generator():
        queue = broadcast.subscribe()
        try:
            yield f"data: {json.dumps(_build_latest_payload())}\n\n"
            while True:
                payload = await queue.get()
                yield f"data: {json.dumps(payload)}\n\n"
        finally:
            broadcast.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")
