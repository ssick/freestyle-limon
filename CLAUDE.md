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
  polls LibreLinkUp every `FETCH_INTERVAL_SECONDS` (60s), writes results into `app/state.py`,
  and publishes the same payload via `app/broadcast.py` after every fetch (success or error).
  `GET /api/latest` reads state back out — it never calls LibreLinkUp itself. `GET /api/stream`
  (Server-Sent Events) pushes that same payload to any number of subscribers the instant
  `fetch_loop` publishes it, plus an immediate on-connect snapshot so a newly-opened
  subscriber isn't blank until the next fetch. Both endpoints share one payload-building
  function, `_build_latest_payload()`, so they can't drift apart. `GET /` and `/static/*` serve
  the frontend.
- **`app/broadcast.py`** — in-memory pub/sub (`set[asyncio.Queue]`) backing `/api/stream`. No
  locking, which is safe only because the app is always single-process/single-uvicorn-worker
  (dev `--reload`, or embedded in `run.py`) — if that ever changes, this needs a cross-process
  broker (e.g. Redis pub/sub) instead of an in-memory set.
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
  charting library. `GET /api/stream` exists but isn't consumed yet — neither page nor the
  Dock icon (`run.py`) has been switched to `EventSource`; that's a planned follow-up
  increment to close the sync gap between windows described in the `app/main.py` bullet above.
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
- **Build the packaged app with `packaging/build.sh`.** It builds with `--clean` (so no
  leftover PyInstaller state from an earlier build can influence the result) and then
  warns if other bundles sharing this app's identifier are installed elsewhere.
- **A shared `CFBundleIdentifier` makes Finder launch the WRONG BINARY.** Not the wrong
  window, not the wrong focus — a genuinely different executable. Double-clicking
  `dist/Freestyle Limón.app` started
  `.claude/worktrees/agent-*/dist/freestyle-limon.app` instead, and only that one process
  ran; the double-clicked bundle never started at all. `open <path>` from a shell always
  gets it right, because an explicit path bypasses identifier resolution. That asymmetry —
  Finder wrong, terminal right, same bundle — is the signature of this bug.
  - **The giveaway is the menu bar**, which shows `CFBundleName`: `Freestyle Limón` is the
    real build, `freestyle-limon` is a worktree copy. The window title is set by pywebview
    and looks identical either way, so it proves nothing. Confirm with
    `ps -o command= -p <pid>`.
  - **`CFBundleVersion` does not break the tie** when one side omits it. Apple's rule
    prefers the higher version, but with nothing to compare it falls through to what Apple
    documents as choosing "in an unspecified manner", which here reliably picked the
    worktree copy even though `dist/` had `CFBundleVersion=21`.
  - **`lsregister -u` does not hold.** Launching an app re-registers it, so unregistering a
    competing bundle is undone the moment anything starts it. The stale bundle has to stop
    being an `.app` — delete it, or rename it to `.app.disabled`.
- **Do not give every build its own identifier.** It does stop the substitution, but an
  identifier macOS has never seen is refused on first Finder launch — the bare
  "kann nicht geöffnet werden" dialog from `CoreServicesUIAgent` — while `open` from a
  shell still works. That trades a wrong-binary bug for an approval prompt after every
  build. `build.sh` therefore uses few, stable identifiers: the release ID, plus a
  `.worktree` suffix when built from a linked worktree (detected via
  `git rev-parse --git-dir` != `--git-common-dir`).
- **This bug cannot be reproduced from a clean slate.** It needs the competing bundle
  present, so killing everything first and relaunching always "works" and makes the bug look
  imaginary. Reproduce it by deliberately constructing the state: leave the other copy in
  place, launch from Finder, then check `ps -o command=` for the path that actually ran.
- **`mdfind` cannot find duplicate bundles; use `lsregister`.** Spotlight never indexes
  dot-directories, so builds under `.claude/worktrees/*/dist` were invisible to the old
  `mdfind`-based guard in `build.sh` while remaining fully visible to LaunchServices (which
  descends into invisible directories). The guard printed "none found" precisely when it
  mattered. It now parses `lsregister -dump`, which immediately surfaced bundles the old
  check never saw — including one on an unmounted volume (`/Volumes/stan`). Related trap:
  grep those paths case-insensitively, since the bundle is named `Freestyle Limón.app`.

## Testing conventions

- Tests use `fastapi.testclient.TestClient` and monkeypatch `app.state`'s module-level
  variables directly (e.g. `monkeypatch.setattr(state, "_latest", ...)`) rather than mocking
  through dependency injection — follow this pattern for new endpoint tests.
- `tests/test_libre_client.py` fakes the `pylibrelinkup` client with a minimal
  `SimpleNamespace`-based `FakeClient` rather than mocking the library — follow this pattern
  for new LibreLinkUp-response-shaped tests.
- **SSE/streaming endpoints can't be tested through a real request via `TestClient`.**
  `httpx`'s `ASGITransport` (which `TestClient` uses) always runs the ASGI app to completion
  and buffers the full response body before returning anything — so a request to an endpoint
  that streams forever by design (like `/api/stream`) hangs the test forever, no matter which
  client method or timeout you use. Instead, `await` the route function directly and drive its
  `StreamingResponse.body_iterator` manually with `__anext__()`/`aclose()` — see
  `test_stream_sends_initial_snapshot_then_cleans_up_on_close` in `tests/test_api.py`. Also
  note the generator is lazy: code before the first `body_iterator` item (e.g.
  `broadcast.subscribe()`) hasn't run yet right after calling the route function.

## Repository conventions

- Development proceeds increment by increment (see commit history: "Increment N: ...").
  Each increment gets its own feature branch, merged into `main` via a human-approved PR.
- PRs are squash-merged.
