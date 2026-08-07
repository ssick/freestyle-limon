# freestyle-limon

Fetches Freestyle Libre 3 glucose readings via LibreLinkUp and displays them in a browser
or native macOS app.

<img width="400" alt="main window" src="https://github.com/user-attachments/assets/c165fae3-b41f-4d2d-89a4-339894a254ac" />

<img width="137" height="179" alt="floating widget" src="https://github.com/user-attachments/assets/1d13ed5c-d7d9-479e-b216-10df76e31448" />

## Disclaimer

This is an unofficial, independent project and is not affiliated with, endorsed by, or
supported by Abbott or LibreLinkUp. It uses LibreLinkUp's unofficial API. Your
`LIBRE_EMAIL` / `LIBRE_PASSWORD` credentials are entered via the standalone macOS app's
Settings window and stored in `~/Library/Application Support/Freestyle Limón/credentials.env`;
for the browser-based dev server they are read from a local `.env` file instead. Either way
they are only sent to LibreLinkUp's API to fetch readings — never logged or sent anywhere
else.

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

The dev server is configured entirely through `.env`. Its Settings page is served through
`pywebview` and so is only reachable in the packaged app — if the dev server reports
"No LibreLinkUp credentials - open Settings…", set `LIBRE_EMAIL` / `LIBRE_PASSWORD` in
`.env` instead.

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

There are two build scripts:

- **`packaging/build.sh`** — quick single-arch build using this repo's own `.venv`. Only
  runs on the same OS version and CPU architecture as the machine that built it. Good for
  local testing:
  ```bash
  ./packaging/build.sh
  ```
- **`packaging/build_universal2.sh`** — the portable build described above (arm64 +
  x86_64, macOS 10.13+). Requires a separate, non-pyenv Python interpreter, because
  building against a single-arch `pyenv`-built Python (as `.venv` uses for everything
  else in this repo) produces a `.app` that only runs on the exact same OS version and
  CPU architecture as the build machine:
  1. Install [python.org's official Python 3.12.9 universal2 installer](https://www.python.org/ftp/python/3.12.9/python-3.12.9-macos11.pkg) (despite the `macos11` in the filename, python.org documents this as requiring macOS 10.13+). This installs to `/Library/Frameworks/Python.framework`, separate from `pyenv` — it won't affect the dev environment set up above.
  2. Run the build script:
     ```bash
     ./packaging/build_universal2.sh
     ```
     This creates its own `.venv-build` venv from that Python, installs dependencies,
     merges the two pinned dependencies that don't ship universal2 wheels on PyPI
     (`Pillow` and `pydantic_core` — merged from separate arm64/x86_64 wheels via
     [`delocate-merge`](https://github.com/matthew-brett/delocate)), and runs PyInstaller.

Either script produces `dist/Freestyle Limón.app`, builds with `--clean` (so no leftover
PyInstaller state from an earlier build can influence the result), and then warns if any
*other* copy of the app is installed elsewhere — see the caution below.

> **Only keep one copy of the app installed.** macOS resolves applications by their
> bundle identifier, not by path. If a second bundle with the same identifier exists
> anywhere (say, an older build sitting in `/Applications`), double-clicking your
> freshly-built `.app` can silently launch the *other* one instead — so a rebuild
> appears to change nothing, and features that are demonstrably present in the new
> binary seem to be missing. If you keep a copy in `/Applications`, replace it after
> every rebuild rather than running the two side by side.

To use the built app:

1. Copy `dist/Freestyle Limón.app` to wherever you want to run it from (e.g. `/Applications`) — replacing any previous copy, per the caution above.
2. Double-click it. It opens as a normal Mac app — no Terminal window, no browser tab — showing the dashboard in its own window. Quit via the window's close button or Cmd+Q.
3. On first launch, open its **Freestyle Limón → Settings…** menu to enter your `LIBRE_EMAIL` / `LIBRE_PASSWORD`. This is the only way to configure the packaged app — it does not read `.env` files. The credentials are stored per-user in `~/Library/Application Support/Freestyle Limón/credentials.env` and survive rebuilds and reinstalls.
