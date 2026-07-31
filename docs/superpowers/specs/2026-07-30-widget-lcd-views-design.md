# Floating widget: switchable LCD views (value / trend / graph)

## Goal

The free-floating macOS widget (`static/widget.html`, opened via `WidgetApi.toggle_widget()`
in `run.py`) currently shows only the current glucose value in its LCD area. Extend it so
clicking the LCD cycles through three views:

1. Current value (today's behavior)
2. Trend arrow
3. 12-hour history graph

This applies **only** to the floating widget. The main dashboard (`static/index.html`) is
unchanged.

## Data flow & state

No backend changes are needed. `GET /api/latest` already returns `trend` (a Unicode arrow
character, e.g. `→`, `↑`, `↓`, sourced from `measurement.trend.indicator` in
`app/libre_client.py`) and `history` (LibreLinkUp's graph endpoint already returns ~12h of
points via the single `read()` call `fetch_reading_and_history()` makes).

`widget.html` adds:

- `currentView`: `'value' | 'trend' | 'graph'`, module-level, starts at `'value'`.
- `lastData`: the most recent successful `/api/latest` payload, module-level.

`poll()` keeps its existing 30s interval (falling back to 2s retry until first success),
storing the response into `lastData` and calling a single `render()` function instead of
writing to `#lemon-digits` directly. A click handler on `#lemon-screen` advances
`currentView` in the fixed order `value → trend → graph → value` and calls `render()`
immediately — no network fetch is needed since it just re-renders `lastData`.

## The three view renderers

`render()` dispatches on `currentView`, always operating on `lastData`:

- **`value`**: `#lemon-digits` shows `data.value` in the DSEG7 font, colored via the
  existing `statusColor(is_high, is_low)`. Unchanged from today.
- **`trend`**: `#lemon-digits` shows `data.trend` in the same DSEG7 font/size and
  `statusColor`. If `data.trend` is `null`, falls back to `--`.
- **`graph`**: replaces the digits element's content with a small inline `<svg>` sized to
  `#lemon-screen`, rendering `data.history` (plus the live current point appended if it's
  newer than the last history point — same logic `index.html` already uses) as a
  simplified sparkline:
  - Line + light area fill in a single neutral color (matching `index.html`'s chart:
    `#5C4A00` line, `0.1` opacity fill).
  - Dots colored per-point via `statusColor(point.is_high, point.is_low)`.
  - No axis labels, no target-range threshold lines, no hover/tooltip.
  - If there's no history yet, shows `--` via the digits element instead of an empty SVG.

All three views share the same `#lemon-screen` box; only its inner content swaps. The box
itself does not resize.

## Interaction & edge cases

- Only `#lemon-screen` is clickable — not the whole `.lemon-wrap` — so clicking elsewhere
  on the lemon body still just drags the frameless window (`easy_drag`, unaffected).
- `#lemon-screen` gets `cursor: pointer` to signal it's interactive, matching the
  `widget-toggle` affordance already used on `index.html`'s lemon.
- Cycling views is instant and local — no fetch on click.
- Before the first successful reading, `lastData` is unset, so all three views show `--`
  (today's pending-state behavior). Clicking still advances `currentView` so the right view
  renders once data arrives.
- `index.html` is untouched — no shared code changes, this is scoped to `widget.html`.

## Testing

This repo has no frontend test suite (`pytest` only covers `app/`). Verification is a live
smoke test per this project's existing convention for frontend work: run the dev server (or
the packaged app), open the widget, and click through all three views checking rendering,
colors, and the drag/click boundary on `#lemon-screen` vs. the rest of the lemon.
