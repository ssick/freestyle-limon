# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See `README.md` for setup, running the dev server, running the full test suite, and building
the standalone macOS app.

## Commands

- Run a single test file: `pytest tests/test_api.py`
- Run a single test: `pytest tests/test_api.py::test_latest_returns_seeded_reading`

## Architecture

This is a single-process FastAPI app with no database and no frontend build step.

- **`app/main.py`** — FastAPI app. A background `fetch_loop()` task (started in `lifespan`)
  polls LibreLinkUp every `FETCH_INTERVAL_SECONDS` (60s) and writes results into `app/state.py`.
  The single `GET /api/latest` endpoint just reads that state back out — it never calls
  LibreLinkUp itself. `GET /` and `/static/*` serve the frontend.
- **`app/state.py`** — process-global in-memory state (module-level variables, not a class/DB).
  Holds the latest reading, recent history, the patient's target range, and the last fetch
  error. Single-patient only: there's no concept of multiple users or sessions.
- **`app/libre_client.py`** — wraps `pylibrelinkup`. `build_client()` authenticates and retries
  once against the region from a `RedirectError` (non-US accounts get redirected on first
  login). `fetch_reading_and_history()` deliberately uses the deprecated `read()` method
  instead of `latest()` + `graph()`, since those two hit the same underlying endpoint
  independently — `read()` gets both in one call.
- **LibreLinkUp's `isHigh`/`isLow` flags are unreliable** on both the current reading and
  historical points (observed `False` even when the value is outside the target range).
  Range status (high/low/in-range) must always be derived by comparing `value` against
  `target_low`/`target_high` from the connection — never trust the API's own flags. See the
  tests in `test_libre_client.py` for the specific cases this covers.
- **Frontend** (`static/index.html`, `static/widget.html`) is vanilla JS/SVG, no framework, no
  build step. Both pages independently poll `/api/latest` every 30s (falling back to a 2s
  retry until the first successful reading) and render client-side. The history chart in
  `index.html` is hand-rolled SVG (scales, hover/tooltip, threshold lines) rather than a
  charting library.
- **`run.py`** is a separate entry point (not used by `uvicorn --reload`) for the packaged
  desktop app: it runs the same FastAPI `app` via `uvicorn` in a background thread inside a
  `pywebview` window, and exposes a `WidgetApi` as `window.pywebview.api` so the page can
  toggle a second frameless "floating widget" window. `window.pywebview` only exists after
  the page finishes loading — code that depends on it (see `setupWidgetToggle` in
  `index.html`) must gate on the `pywebviewready` event, not check for it synchronously.
- **Packaging** (`freestyle-limon.spec`, built with `pyinstaller`) bundles `static/` into the
  app. When frozen (`sys.frozen`), `app/main.py` resolves `.env` relative to
  `sys.executable`'s bundle location instead of `__file__`, since PyInstaller extracts the
  source into a temp dir at runtime — see the comment at the top of `app/main.py` for the
  exact path-walking logic.
- **The packaged app must be built as `target_arch='universal2'`** (set in
  `freestyle-limon.spec`), via `packaging/build_universal2.sh`, not by running
  `pyinstaller` directly against the `pyenv`-managed `.venv`. `pyenv` builds a
  single-architecture Python targeting whatever OS it was compiled on — on this repo's
  dev machines that's arm64 with a very high deployment target, which produces a `.app`
  that only runs on that same OS/arch. The build script uses a separate python.org
  universal2 Python instead. `Pillow` and `pydantic_core` don't publish universal2 wheels
  on PyPI (only separate arm64/x86_64 ones), so the script merges them with
  `delocate-merge` before running PyInstaller — see the script's comments for the exact
  mechanism, and its `THIN_PACKAGES` list if a future dependency bump introduces another
  one (PyInstaller's `IncompatibleBinaryArchError` names the offending file when this
  happens). `LSMinimumSystemVersion` in the spec is `10.13` — the practical floor of the
  entire current Python/PyInstaller/pyobjc packaging ecosystem, confirmed by checking the
  actual PyPI wheel tags and PyInstaller's bootloader default, not an arbitrary choice.

## Testing conventions

- Tests use `fastapi.testclient.TestClient` and monkeypatch `app.state`'s module-level
  variables directly (e.g. `monkeypatch.setattr(state, "_latest", ...)`) rather than mocking
  through dependency injection — follow this pattern for new endpoint tests.
- `tests/test_libre_client.py` fakes the `pylibrelinkup` client with a minimal
  `SimpleNamespace`-based `FakeClient` rather than mocking the library — follow this pattern
  for new LibreLinkUp-response-shaped tests.

## Repository conventions

- Development proceeds increment by increment (see commit history: "Increment N: ...").
  Each increment's feature branch is merged into `main` via a human-approved PR before the
  next increment starts — always branch from `main`, not from a previous increment's branch.
- PRs are squash-merged. Don't stack a new branch on top of an unmerged one — after a squash
  merge, the stacked branch's shared-file history diverges from `main` and produces spurious
  "both added" conflicts on sync. Wait for the PR to merge first.
