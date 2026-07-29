# freestyle-limon

Fetches Freestyle Libre 3 glucose readings via LibreLinkUp and displays them in a browser.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in LIBRE_EMAIL / LIBRE_PASSWORD
```

## Run

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

Open http://localhost:8000

## Test

```bash
source .venv/bin/activate
pytest
```

## Standalone macOS app

For running without a Python install, build a single executable:

```bash
source .venv/bin/activate
pip install -r requirements-build.txt
pyinstaller --onefile --name freestyle-limon --add-data "static:static" run.py
```

This produces `dist/freestyle-limon`. To use it:

1. Copy `dist/freestyle-limon` and `.env.example` to wherever you want to run it from.
2. Rename `.env.example` to `.env` next to the executable and fill in `LIBRE_EMAIL` / `LIBRE_PASSWORD`.
3. Run `./freestyle-limon` (or double-click it in Finder). It starts the server and opens http://localhost:8000 in your browser automatically.
