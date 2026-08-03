# freestyle-limon

Fetches Freestyle Libre 3 glucose readings via LibreLinkUp and displays them in a browser
or native macOS app.

<img width="400" alt="main window" src="https://github.com/user-attachments/assets/c165fae3-b41f-4d2d-89a4-339894a254ac" />

<img width="137" height="179" alt="floating widget" src="https://github.com/user-attachments/assets/1d13ed5c-d7d9-479e-b216-10df76e31448" />

## Disclaimer

This is an unofficial, independent project and is not affiliated with, endorsed by, or
supported by Abbott or LibreLinkUp. It uses LibreLinkUp's unofficial API. Your
`LIBRE_EMAIL` / `LIBRE_PASSWORD` credentials are read from a local `.env` file (or, in the
standalone macOS app, entered via its Settings window and stored in
`~/Library/Application Support/Freestyle Limón/credentials.env`) and are only sent to
LibreLinkUp's API to fetch readings — never logged or sent anywhere else.

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
./packaging/build.sh
```

This produces `dist/Freestyle Limón.app`. Always build with this script rather than
running `pyinstaller freestyle-limon.spec` directly — PyInstaller keeps a cache at
`~/Library/Application Support/pyinstaller/` that's shared across every PyInstaller
project on the machine, not just this repo, and a build using a stale copy of it can
report success while silently omitting code (e.g. a native menu item that's correctly
present in the source but missing from the built app). The script always passes
`--clean`, which purges that cache (and the local `build/` one) before building, so the
result is guaranteed to reflect the current source tree.

To use the built app:

1. Copy `dist/Freestyle Limón.app` to wherever you want to run it from (e.g. `/Applications`).
2. Double-click it. It opens as a normal Mac app — no Terminal window, no browser tab — showing the dashboard in its own window. Quit via the window's close button or Cmd+Q.
3. On first launch, open its **Freestyle Limón → Settings…** menu to enter your `LIBRE_EMAIL` / `LIBRE_PASSWORD` — no `.env` file needed. (A `.env` placed next to the `.app`, the old setup method, still works as a fallback if you already have one.)
