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
- **Frontend** (`static/index.html`, `static/widget.html`, `static/settings.html`) is vanilla
  JS/SVG, no framework, no build step. `index.html` and `widget.html` subscribe to
  `GET /api/stream` via `EventSource` and render client-side on each push. The history chart
  in `index.html` is hand-rolled SVG (scales, hover/tooltip, threshold lines) rather than a
  charting library.
- **Frontend JS must not use syntax newer than Safari 13.1** (no `?.`, `??`, `||=`/`&&=`/`??=`,
  etc.), even though `LSMinimumSystemVersion` is 10.13 and Safari 13.1.2 (which supports all
  of that) is the newest Safari Apple ever shipped for 10.13. Real machines still on 10.13
  aren't guaranteed to have taken that update — one test machine turned out to be on Safari
  11.1 (WebKit build `13605.3.8`, from 2018). WKWebView loads the *system* WebKit.framework,
  not something the app bundles, so this isn't fixable by the app at all. A single
  unsupported-syntax `SyntaxError` anywhere in an inline `<script>` block silently aborts the
  entire block — every symptom looks unrelated (an `EventSource` that never connects, a click
  handler that never attaches, a form submit that silently does nothing) but traces back to
  one parse failure. `tests/test_status_color.py`-style static regression tests don't catch
  this, since evaluating the JS engine's parser behavior needs a real (old) WebKit, not a
  Python string check - your best bet is a real 10.13 machine.
- **`static/lemon.svg` is a traced image, not a designed vector** — 15 stacked opaque colour
  layers with no outline and no single base shape, so the artwork's silhouette is only the
  *union* of those layers. Its first path (`id="lemon-backing"`) is a generated opaque
  silhouette of that union, dilated by ~1.5 user units, that exists purely so nothing behind
  the SVG can show through: on a light page a hairline seam where two layers abut is
  invisible, but the widget floats over the desktop (`transparent=True` in `run.py`), and on
  a dark desktop the same seams read as the background bleeding through the fruit. It was
  produced by rasterising the artwork, dilating the alpha mask and contour-tracing it — if
  the artwork is ever re-exported, regenerate the backing path rather than hand-editing it.
- **`run.py`** is a separate entry point (not used by `uvicorn --reload`) for the packaged
  desktop app: it runs the same FastAPI `app` via `uvicorn` in a background thread inside a
  `pywebview` window, and exposes a `WidgetApi` as `window.pywebview.api` so the page can
  toggle a second frameless "floating widget" window. `window.pywebview` only exists after
  the page finishes loading — code that depends on it (see `setupWidgetToggle` in
  `index.html`) must gate on the `pywebviewready` event, not check for it synchronously.
- **`run.py` patches `WKNavigationAction` on startup** (`_patch_webkit_navigation_action_for_old_webkit`)
  to work around a pywebview 6.2.1 bug that leaves the main window permanently blank on
  macOS 10.13: pywebview's Cocoa navigation delegate unconditionally calls
  `WKNavigationAction.shouldPerformDownload()`, a selector Apple only added in macOS 11.3.
  On 10.13 it doesn't exist, so the call raises inside the delegate callback before the
  completion handler is invoked — WebKit is left waiting forever for a navigation decision
  (visible in Console.app as WebCore's `DocumentLoader::startLoadingMainResource: Returning
  empty document`, plus a "Completion handler ... was not called" warning when the delegate
  is later deallocated), so the window never renders anything, even though the app process
  itself is fine (e.g. the Dock icon, which is drawn independently in Python/AppKit, keeps
  updating). There's no pywebview release newer than 6.2.1 with a fix, and the last version
  before this call was added (5.3.2) is over a year of other fixes behind, so this patches
  the gap instead of downgrading. The fix adds the missing `shouldPerformDownload` selector
  directly onto `WKNavigationAction` (returning `False`) via `objc.classAddMethods`, rather
  than reassigning pywebview's delegate method itself — that was tried first and crashed
  with `TypeError: cannot call block without a signature`, since the delegate method's
  `handler` argument is an Objective-C block, and reassigning the method loses the block's
  bridging metadata that PyObjC only wires up when the class is originally defined.
- **Packaging** (`freestyle-limon.spec`, built with `pyinstaller`) bundles `static/` into the
  app. Note that when frozen, `__file__` resolves inside PyInstaller's temp extraction dir
  rather than next to the launched binary, so it can't be used to locate anything the user
  placed on disk.
- **Credentials come from a different place in each runtime.** The packaged app reads only
  `~/Library/Application Support/Freestyle Limón/credentials.env` via `app/credentials.py`,
  written by the Settings window; `app/main.py` skips `.env` entirely when `sys.frozen`. The
  browser-based dev server reads the repo-root `.env` and has no other option, because
  `static/settings.html` saves through `window.pywebview.api.save_credentials()` and there is
  no HTTP route for it. A packaged build previously also looked for a `.env` in the folder
  *containing* the `.app` — that was removed, since it resolves to `/Applications` for a
  normal install and mainly served to produce a "check your .env file" error that sent users
  hunting for a file they never had.
- **Two build scripts share `freestyle-limon.spec`.** `target_arch` and
  `LSMinimumSystemVersion` in the spec are read from the `FREESTYLE_LIMON_TARGET_ARCH` /
  `FREESTYLE_LIMON_MIN_MACOS` env vars (defaulting to `universal2` / `10.13`), because the
  two scripts need different values from the same spec file — see each script's own
  comments:
  - **`packaging/build.sh`** — quick single-arch build against this repo's own
    `pyenv`-managed `.venv`, for local testing. Overrides the env vars back to a plain
    single-arch build targeting `11.0`, since `pyenv` builds a single-architecture Python
    targeting whatever OS it was compiled on (on this repo's dev machines, arm64 with a
    very high deployment target) — requesting `universal2` against that interpreter fails
    with PyInstaller's `IncompatibleBinaryArchError`, since the interpreter itself is only
    one arch's slice. It builds with `--clean` (so no leftover PyInstaller state from an
    earlier build can influence the result), derives this build's bundle identifier and
    version (see the "duplicate bundles" bullets below), and warns if any other bundle
    registered with macOS still shares the resulting identifier.
  - **`packaging/build_universal2.sh`** — the portable release build: `target_arch=` is
    left at its `universal2` default, producing a `.app` that runs on **macOS 10.13+** on
    both Intel and Apple Silicon (the practical floor of the entire current
    Python/PyInstaller/pyobjc packaging ecosystem, confirmed by checking the actual PyPI
    wheel tags and PyInstaller's bootloader default, not an arbitrary choice). Requires a
    separate python.org universal2 Python instead of `pyenv`'s. `Pillow` and
    `pydantic_core` don't publish universal2 wheels on PyPI (only separate arm64/x86_64
    ones), so the script merges them with `delocate-merge` before running PyInstaller —
    see the script's comments for the exact mechanism, and its `THIN_PACKAGES` list if a
    future dependency bump introduces another one (PyInstaller's
    `IncompatibleBinaryArchError` names the offending file when this happens). Derives the
    same bundle identifier and version as `build.sh` (same logic, duplicated rather than
    shared between two standalone shell scripts), but doesn't repeat `build.sh`'s
    LaunchServices registration/duplicate-copy check — that's about the fast local-iteration
    loop this script isn't meant for.
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
  - **`CFBundleVersion` is what decides the winner, and it is load-bearing.** Measured with
    two bundles sharing the identifier and differing only in version (21 vs 10):
    double-clicking *either* one launched the **higher-versioned** bundle, confirmed via
    the About panel and `CFBundleName` in the menu bar. Apple's documented "prefer the
    latest `CFBundleVersion`" rule does apply to launching an app, not only to opening
    documents.
  - **A missing `CFBundleVersion` is not treated as "lowest" — it breaks the rule.** The
    worktree bundle had none at all, so even against `dist/` at version 21 it still won:
    with one side absent there is nothing to compare and macOS falls through to what its
    own docs call choosing "in an unspecified manner". So the shared identifier was
    necessary but not sufficient; the absent version is what let the wrong binary win.
    **Never ship a build without `CFBundleVersion`** — `build.sh` sets it from
    `git rev-list --count HEAD`. This is also what protects end users who keep an old copy
    alongside a new one: double-clicking either runs the newest installed build.
  - **`lsregister -u` does not hold.** Launching an app re-registers it, so unregistering a
    competing bundle is undone the moment anything starts it. The stale bundle has to stop
    being an `.app` — delete it, or rename it to `.app.disabled`.
- **`build.sh` uses few, stable identifiers**: the release ID, plus a `.worktree` suffix
  when built from a linked worktree (detected via `git rev-parse --git-dir` !=
  `--git-common-dir`). Combined with `CFBundleVersion` this is sufficient, so there is no
  reason to mint an identifier per build.
- **Changing a bundle's identifier at a path LaunchServices already knows poisons that
  path.** Finder then refuses the app outright — the bare "kann nicht geöffnet werden"
  dialog from `CoreServicesUIAgent` — while `open <path>` still launches it fine. Proven
  by a single-variable test: one bundle at one path launched normally as `…​.exp1`, was
  given the identifier `…​.exp2` in place (re-signed, valid, no competing bundle), and was
  then refused. This is exactly what a per-build identifier does to `dist/` on every
  build, and it is why per-build identifiers are unusable here.
  - **`lsregister` cannot repair it.** `-f` leaves the database and the bundle agreeing on
    the new identifier and the app is still refused; `-u` fails outright on this path with
    `-10814` (`kLSApplicationNotFoundErr`).
  - **The remedy is a new path.** The same poisoned bundle copied to a directory
    LaunchServices has never seen launches normally. So if an app's identifier ever has to
    change, ship it at a new location rather than overwriting the old one in place.
  - Ruled out along the way, all by measurement: Gatekeeper and ad-hoc signing (a
    perfectly working bundle also assesses as `rejected`), quarantine and translocation
    (no xattr), a broken signature (`codesign --verify` passes), a crash (no crash report,
    and it runs fine under a minimal Finder-like environment), and identifier novelty
    itself (a brand-new identifier at a *fresh* path launches normally).
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
