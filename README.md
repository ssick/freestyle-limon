# freestyle-limon

Fetches Freestyle Libre 3 glucose readings via LibreLinkUp and displays them in a browser
or native macOS app.

<img width="400" alt="main window" src="https://github.com/user-attachments/assets/c165fae3-b41f-4d2d-89a4-339894a254ac" />

<img width="137" height="179" alt="floating widget" src="https://github.com/user-attachments/assets/1d13ed5c-d7d9-479e-b216-10df76e31448" />

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

For running without a Python install, build a native `.app`. The build produces a
**universal2** binary (arm64 + x86_64) that runs on **macOS 10.13 or later** — this is
close to the oldest macOS the current Python packaging ecosystem can target at all
(Python 3.13+ and most compiled-dependency wheels have moved their own floor to 10.13).

This requires a separate, non-pyenv Python interpreter, because building against a
single-arch `pyenv`-built Python (as `.venv` uses for everything else in this repo)
produces a `.app` that only runs on the exact same OS version and CPU architecture as
the build machine:

1. Install [python.org's official Python 3.12.9 universal2 installer](https://www.python.org/ftp/python/3.12.9/python-3.12.9-macos11.pkg) (despite the `macos11` in the filename, python.org documents this as requiring macOS 10.13+). This installs to `/Library/Frameworks/Python.framework`, separate from `pyenv` — it won't affect the dev environment set up above.
2. Run the build script:
   ```bash
   ./packaging/build_universal2.sh
   ```
   This creates its own `.venv-build` venv from that Python, installs dependencies,
   merges the two pinned dependencies that don't ship universal2 wheels on PyPI
   (`Pillow` and `pydantic_core` — merged from separate arm64/x86_64 wheels via
   [`delocate-merge`](https://github.com/matthew-brett/delocate)), and runs PyInstaller.

This produces `dist/Freestyle Limón.app`. To use it:

1. Copy `dist/Freestyle Limón.app` and `.env.example` to wherever you want to run it from (e.g. `/Applications`).
2. Rename `.env.example` to `.env`, placed next to `Freestyle Limón.app` (not inside the bundle), and fill in `LIBRE_EMAIL` / `LIBRE_PASSWORD`.
3. Double-click `Freestyle Limón.app`. It opens as a normal Mac app — no Terminal window, no browser tab — showing the dashboard in its own window. Quit via the window's close button or Cmd+Q.
