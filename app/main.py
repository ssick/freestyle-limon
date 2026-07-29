import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse

from app import state
from app.libre_client import build_client, fetch_latest_reading

load_dotenv()

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
            reading = await asyncio.to_thread(fetch_latest_reading, client, patient)
            state.set_latest(reading)
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


@app.get("/api/latest")
async def get_latest():
    reading = state.get_latest()
    if reading is None:
        return {"status": "pending"}
    return {
        "status": "ok",
        "value": reading.value,
        "trend": reading.trend,
        "timestamp": reading.timestamp,
        "is_high": reading.is_high,
        "is_low": reading.is_low,
    }


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")
