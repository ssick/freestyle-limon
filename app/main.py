import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import state
from app.libre_client import build_client, fetch_reading_and_history

# When frozen into a standalone executable, __file__ resolves inside the
# PyInstaller temp extraction dir, not next to the binary the user launched -
# so .env has to be looked up relative to sys.executable in that case instead.
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent

load_dotenv(APP_DIR / ".env")

logger = logging.getLogger("freestyle_limon")

FETCH_INTERVAL_SECONDS = 60
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


async def fetch_loop() -> None:
    client = None
    patient = None
    while True:
        try:
            if client is None:
                client, patient = await asyncio.to_thread(build_client)
            reading, history, target_low, target_high = await asyncio.to_thread(
                fetch_reading_and_history, client, patient
            )
            state.set_latest(reading)
            state.set_history(history)
            state.set_target_range(target_low, target_high)
            logger.info("Fetched glucose reading: %s", reading)
        except Exception:
            logger.exception("Failed to fetch glucose reading")
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
        return {"status": "pending"}
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
