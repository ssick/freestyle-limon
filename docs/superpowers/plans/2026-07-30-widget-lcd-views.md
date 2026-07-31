# Widget switchable LCD views Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let clicking the LCD area on the free-floating macOS widget cycle through three
views — current value, trend arrow, and a 12h history sparkline.

**Architecture:** Pure frontend change in `static/widget.html`. `/api/latest` already
returns everything needed (`trend`, `history`); no backend changes. The script gains a
`currentView` string cycled by a click handler on `#lemon-screen`, a `lastData` cache of
the latest poll response, and a `render()` dispatcher that swaps the LCD's inner content
between a digits `<span>` (value/trend) and an inline `<svg>` (graph).

**Tech Stack:** Vanilla JS/HTML/CSS, no build step, no frontend test framework (this repo
only has `pytest` for `app/`).

## Global Constraints

- Only `static/widget.html` is modified. `static/index.html` and everything under `app/`
  are untouched.
- No backend changes — `trend` and `history` are already present in the `/api/latest`
  response (see `app/main.py:71-95`).
- The widget window never resizes for any view — it stays the fixed 180×180 created in
  `run.py:42-56`. Only `#lemon-screen`'s inner content changes.
- Click target for cycling is `#lemon-screen` only, not the whole `.lemon-wrap` — clicking
  elsewhere on the lemon body must keep working as window drag (`easy_drag` in `run.py`).
- Cycle order is fixed: `value → trend → graph → value → ...`.
- Graph view is a simplified sparkline only: line + area fill + per-point colored dots.
  No axis labels, no target-range threshold lines, no hover/tooltip.
- No automated frontend test suite exists in this repo. Every task is verified by a live
  smoke test: run the dev server (`uvicorn app.main:app --reload`, per `README.md`) and
  open `http://localhost:8000/static/widget.html` in a normal browser tab — this file
  doesn't touch `window.pywebview`, so it renders fine outside the packaged app for
  development purposes. Use the browser devtools console to poke `lastData`/`currentView`
  and call `render()` directly where real LibreLinkUp data isn't available in dev.

---

### Task 1: State refactor — introduce `lastData` and `renderValue()`, no behavior change

**Files:**
- Modify: `static/widget.html:37-65` (the `<script>` block)

**Interfaces:**
- Produces: `renderValue()` — reads module-level `lastData` (the last successful
  `/api/latest` JSON response, or `null`) and writes into `#lemon-digits`. Later tasks call
  this from a `render()` dispatcher.
- Produces: `lastData` — module-level variable, `null` until the first successful poll,
  thereafter the full `/api/latest` response object.

- [ ] **Step 1: Replace the script block**

Replace the existing `<script>...</script>` block (currently `static/widget.html:37-65`)
with:

```html
  <script>
    function statusColor(isHigh, isLow) {
      return isHigh ? 'orange' : isLow ? 'red' : 'green';
    }

    let lastData = null;

    function renderValue() {
      const digitsEl = document.getElementById('lemon-digits');
      if (lastData) {
        digitsEl.textContent = lastData.value;
        digitsEl.style.color = statusColor(lastData.is_high, lastData.is_low);
      } else {
        digitsEl.textContent = '--';
      }
    }

    let hasReading = false;
    const POLL_INTERVAL_MS = 30000;
    const RETRY_INTERVAL_MS = 2000;

    async function poll() {
      try {
        const res = await fetch('/api/latest');
        const data = await res.json();
        if (data.status === 'ok') {
          hasReading = true;
          lastData = data;
        }
        renderValue();
      } catch (err) {
        console.error('Failed to poll /api/latest', err);
      } finally {
        setTimeout(poll, hasReading ? POLL_INTERVAL_MS : RETRY_INTERVAL_MS);
      }
    }

    poll();
  </script>
```

This preserves today's exact behavior: on a successful poll the value renders
color-coded; on a pending/error poll, whatever was last rendered stays on screen (now via
`lastData` persisting rather than simply skipping the DOM write).

- [ ] **Step 2: Live smoke test**

Run: `uvicorn app.main:app --reload` (from repo root, with the venv active per
`README.md`).

In a second terminal: `curl -s http://localhost:8000/api/latest` — confirm it returns
JSON with `"status"` of `"ok"` or `"pending"`.

Open `http://localhost:8000/static/widget.html` in a browser tab.

Expected: the LCD shows either a color-coded numeric value (if `LIBRE_EMAIL`/
`LIBRE_PASSWORD` are configured and a reading has been fetched) or `--` (if pending) —
identical to the widget's behavior before this change. No errors in the browser console.

- [ ] **Step 3: Commit**

```bash
git add static/widget.html
git commit -m "Refactor widget LCD rendering to read from cached lastData"
```

---

### Task 2: Add trend view and click-to-cycle (value ↔ trend)

**Files:**
- Modify: `static/widget.html:22-27` (the `#lemon-screen` CSS rule)
- Modify: `static/widget.html` script block (from Task 1)

**Interfaces:**
- Consumes: `lastData`, `statusColor()`, `renderValue()` from Task 1.
- Produces: `currentView` — module-level string, one of `'value' | 'trend'` (extended to
  include `'graph'` in Task 3).
- Produces: `renderTrend()`, `render()`, `cycleView()` — `render()` is the dispatcher later
  tasks and the poll loop call instead of calling a specific view renderer directly.

- [ ] **Step 1: Add `cursor: pointer` to the LCD area**

In the `#lemon-screen` CSS rule (`static/widget.html:22-27`), add a `cursor` declaration:

```css
  #lemon-screen {
    position: absolute;
    left: 24.24%; top: 38.95%; width: 52.73%; height: 22.79%;
    border-radius: 6% / 9%;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
  }
```

- [ ] **Step 2: Add trend view, dispatcher, and click cycling**

Replace the script block from Task 1 with:

```html
  <script>
    function statusColor(isHigh, isLow) {
      return isHigh ? 'orange' : isLow ? 'red' : 'green';
    }

    const VIEW_ORDER = ['value', 'trend'];
    let currentView = 'value';
    let lastData = null;

    function renderValue() {
      const digitsEl = document.getElementById('lemon-digits');
      if (lastData) {
        digitsEl.textContent = lastData.value;
        digitsEl.style.color = statusColor(lastData.is_high, lastData.is_low);
      } else {
        digitsEl.textContent = '--';
      }
    }

    function renderTrend() {
      const digitsEl = document.getElementById('lemon-digits');
      if (lastData && lastData.trend) {
        digitsEl.textContent = lastData.trend;
        digitsEl.style.color = statusColor(lastData.is_high, lastData.is_low);
      } else {
        digitsEl.textContent = '--';
      }
    }

    function render() {
      if (currentView === 'trend') renderTrend();
      else renderValue();
    }

    function cycleView() {
      const idx = VIEW_ORDER.indexOf(currentView);
      currentView = VIEW_ORDER[(idx + 1) % VIEW_ORDER.length];
      render();
    }

    let hasReading = false;
    const POLL_INTERVAL_MS = 30000;
    const RETRY_INTERVAL_MS = 2000;

    async function poll() {
      try {
        const res = await fetch('/api/latest');
        const data = await res.json();
        if (data.status === 'ok') {
          hasReading = true;
          lastData = data;
        }
        render();
      } catch (err) {
        console.error('Failed to poll /api/latest', err);
      } finally {
        setTimeout(poll, hasReading ? POLL_INTERVAL_MS : RETRY_INTERVAL_MS);
      }
    }

    document.getElementById('lemon-screen').addEventListener('click', cycleView);
    poll();
  </script>
```

- [ ] **Step 3: Live smoke test**

With the dev server still running, refresh `http://localhost:8000/static/widget.html`.

Click on the LCD area (the small rounded rectangle where the value is displayed, not the
lemon body around it).

Expected: the display toggles between the numeric value and the trend arrow (or `--` if
`lastData.trend` is falsy) on each click, cycling back to value after trend.

Open the browser devtools console on that tab and run:

```js
lastData = { ...lastData, trend: '↑', is_high: false, is_low: false };
currentView = 'trend'; render();
```

Expected: `↑` renders in green. Repeat with `is_high: true` (expect orange) and
`is_low: true` (expect red).

Click somewhere on the lemon body outside the LCD rectangle.

Expected: nothing happens (view does not cycle) — confirms the click listener is scoped
to `#lemon-screen` only.

- [ ] **Step 4: Commit**

```bash
git add static/widget.html
git commit -m "Add trend view and click-to-cycle on the widget LCD"
```

---

### Task 3: Add graph view and extend the cycle to value → trend → graph

**Files:**
- Modify: `static/widget.html:22-29` (add `#lemon-graph` CSS rule)
- Modify: `static/widget.html` script block (from Task 2)

**Interfaces:**
- Consumes: `lastData`, `currentView`, `VIEW_ORDER`, `statusColor()`, `render()`,
  `cycleView()` from Task 2.
- Produces: `historyForGraph()` — returns the array of `{value, timestamp, is_high,
  is_low}` points to plot, appending the live `lastData` reading if it's newer than the
  last history point (same rule `static/index.html` already uses for its full chart).
- Produces: `renderGraph()`, `showDigits()` — `showDigits()` ensures `#lemon-screen`
  contains a `#lemon-digits` span (recreating it if the previous render left an `<svg>` in
  its place) and returns that element; `renderValue()`/`renderTrend()` are updated to call
  it instead of a bare `getElementById`.

- [ ] **Step 1: Add CSS for the graph SVG**

Add this rule after the existing `#lemon-digits` rule in `static/widget.html`'s `<style>`
block:

```css
  #lemon-graph { width: 100%; height: 100%; display: block; }
```

- [ ] **Step 2: Add the graph view and wire it into the cycle**

Replace the script block from Task 2 with:

```html
  <script>
    function statusColor(isHigh, isLow) {
      return isHigh ? 'orange' : isLow ? 'red' : 'green';
    }

    const VIEW_ORDER = ['value', 'trend', 'graph'];
    let currentView = 'value';
    let lastData = null;

    function showDigits() {
      const screen = document.getElementById('lemon-screen');
      if (!document.getElementById('lemon-digits')) {
        screen.innerHTML = '<span id="lemon-digits"></span>';
      }
      return document.getElementById('lemon-digits');
    }

    function renderValue() {
      const digitsEl = showDigits();
      if (lastData) {
        digitsEl.textContent = lastData.value;
        digitsEl.style.color = statusColor(lastData.is_high, lastData.is_low);
      } else {
        digitsEl.textContent = '--';
      }
    }

    function renderTrend() {
      const digitsEl = showDigits();
      if (lastData && lastData.trend) {
        digitsEl.textContent = lastData.trend;
        digitsEl.style.color = statusColor(lastData.is_high, lastData.is_low);
      } else {
        digitsEl.textContent = '--';
      }
    }

    function historyForGraph() {
      if (!lastData) return [];
      let history = (lastData.history ?? []).filter(p => p.timestamp);
      const lastPoint = history[history.length - 1];
      if (lastData.timestamp && (!lastPoint?.timestamp || new Date(lastData.timestamp) > new Date(lastPoint.timestamp))) {
        history = [...history, {
          value: lastData.value,
          timestamp: lastData.timestamp,
          is_high: lastData.is_high,
          is_low: lastData.is_low,
        }];
      }
      return history;
    }

    function renderGraph() {
      const history = historyForGraph();
      const screen = document.getElementById('lemon-screen');

      if (history.length === 0) {
        screen.innerHTML = '<span id="lemon-digits">--</span>';
        return;
      }

      const times = history.map(p => new Date(p.timestamp).getTime());
      const tMin = Math.min(...times), tMax = Math.max(...times);
      const tSpan = Math.max(tMax - tMin, 1);

      const values = history.map(p => p.value);
      const vRawMin = Math.min(...values), vRawMax = Math.max(...values);
      const pad = Math.max((vRawMax - vRawMin) * 0.1, 10);
      const vMin = vRawMin - pad, vMax = vRawMax + pad;
      const vSpan = Math.max(vMax - vMin, 1);

      screen.innerHTML = '<svg id="lemon-graph"></svg>';
      const svg = document.getElementById('lemon-graph');
      const W = screen.clientWidth, H = screen.clientHeight;
      svg.setAttribute('viewBox', `0 0 ${W} ${H}`);

      const xOf = t => ((t - tMin) / tSpan) * W;
      const yOf = v => H - ((v - vMin) / vSpan) * H;

      const points = history.map((p, i) => ({
        x: xOf(times[i]),
        y: yOf(p.value),
        is_high: p.is_high,
        is_low: p.is_low,
      }));

      const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
      const areaPath = `${linePath} L${points[points.length - 1].x.toFixed(1)},${H} L${points[0].x.toFixed(1)},${H} Z`;
      const dots = points.map(p => `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="3" fill="${statusColor(p.is_high, p.is_low)}" />`).join('');

      svg.innerHTML = `
        <path d="${areaPath}" fill="#5C4A00" fill-opacity="0.15" stroke="none" />
        <path d="${linePath}" fill="none" stroke="#5C4A00" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
        ${dots}
      `;
    }

    function render() {
      if (currentView === 'trend') renderTrend();
      else if (currentView === 'graph') renderGraph();
      else renderValue();
    }

    function cycleView() {
      const idx = VIEW_ORDER.indexOf(currentView);
      currentView = VIEW_ORDER[(idx + 1) % VIEW_ORDER.length];
      render();
    }

    let hasReading = false;
    const POLL_INTERVAL_MS = 30000;
    const RETRY_INTERVAL_MS = 2000;

    async function poll() {
      try {
        const res = await fetch('/api/latest');
        const data = await res.json();
        if (data.status === 'ok') {
          hasReading = true;
          lastData = data;
        }
        render();
      } catch (err) {
        console.error('Failed to poll /api/latest', err);
      } finally {
        setTimeout(poll, hasReading ? POLL_INTERVAL_MS : RETRY_INTERVAL_MS);
      }
    }

    document.getElementById('lemon-screen').addEventListener('click', cycleView);
    poll();
  </script>
```

- [ ] **Step 3: Live smoke test — mocked data**

With the dev server running, refresh `http://localhost:8000/static/widget.html`. Open the
devtools console and run:

```js
lastData = {
  status: 'ok', value: 140, is_high: false, is_low: false, trend: '→',
  timestamp: new Date().toISOString(), target_low: 70, target_high: 180,
  history: [
    { value: 100, timestamp: new Date(Date.now() - 3600000).toISOString(), is_high: false, is_low: false },
    { value: 190, timestamp: new Date(Date.now() - 1800000).toISOString(), is_high: true, is_low: false },
  ],
};
currentView = 'graph'; render();
```

Expected: an SVG line + light area fill appears in the LCD area, with two dots — one
green (the 100 point) and one orange (the 190 point, `is_high: true`) — and no console
errors.

Then test the empty-history fallback:

```js
lastData = { ...lastData, history: [], timestamp: null };
render();
```

Expected: the LCD shows `--`.

- [ ] **Step 4: Live smoke test — full cycle**

Reload the page (clears console overrides, restores real polling). Click the LCD three
times in a row.

Expected: value → trend → graph → back to value, each transition instant (no network
request triggered by the click — check the Network tab shows no new `/api/latest` request
at click time). No console errors at any point in the cycle, including when `lastData` is
still `null` (before the first successful poll) or history is empty.

- [ ] **Step 5: Note on native widget verification**

This plan's automated/console-driven smoke tests all run against
`http://localhost:8000/static/widget.html` in a regular browser tab, which is sufficient
to verify the rendering and click logic since `widget.html` doesn't depend on
`window.pywebview`. Confirming the *actual* floating widget window (transparent,
frameless, always-on-top, opened via the lemon toggle in `index.html` while running
`python run.py`) behaves the same way requires a macOS GUI session with real
`LIBRE_EMAIL`/`LIBRE_PASSWORD` credentials configured — flag this to the user as a manual
check to perform themselves if that environment isn't available to you.

- [ ] **Step 6: Commit**

```bash
git add static/widget.html
git commit -m "Add graph view to the widget LCD cycle"
```
