# freestyle-limon

Fetches Freestyle Libre 3 glucose readings via LibreLinkUp and displays them in a browser.

## Disclaimer

This is an unofficial, independent project and is not affiliated with, endorsed by, or
supported by Abbott or LibreLinkUp. It uses LibreLinkUp's unofficial API. Your
`LIBRE_EMAIL` / `LIBRE_PASSWORD` credentials are read from a local `.env` file and are
only sent to LibreLinkUp's API to fetch readings — never logged or sent anywhere else.

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

For running without a Python install, build a native `.app`:

```bash
source .venv/bin/activate
pip install -r requirements-build.txt
pyinstaller freestyle-limon.spec
```

This produces `dist/freestyle-limon.app`. To use it:

1. Copy `dist/freestyle-limon.app` and `.env.example` to wherever you want to run it from (e.g. `/Applications`).
2. Rename `.env.example` to `.env`, placed next to `freestyle-limon.app` (not inside the bundle), and fill in `LIBRE_EMAIL` / `LIBRE_PASSWORD`.
3. Double-click `freestyle-limon.app`. It opens as a normal Mac app — no Terminal window, no browser tab — showing the dashboard in its own window. Quit via the window's close button or Cmd+Q.
