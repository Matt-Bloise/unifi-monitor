# static

Dashboard frontend served by FastAPI at `/`.

## Files

| File | Lines | Purpose |
|------|-------|---------|
| `index.html` | 162 | Dashboard layout: site selector, theme toggle, connection badge, overview cards, comparison panel, client table, chart containers |
| `css/style.css` | 473 | Responsive CSS with dark/light theme via CSS custom properties. Chart.js color synchronization |
| `js/dashboard.js` | 886 | Vanilla JS: WebSocket client, REST fallback, Chart.js rendering, theme persistence, data export |

## Features

- **WebSocket live updates**: Auto-connects to `/api/ws`, green badge when live
- **REST polling fallback**: Falls back to 15s REST polling after 3 WS failures (yellow badge)
- **Auto-reconnect**: Exponential backoff (1s -> 2s -> 4s -> ... -> 30s max)
- **Tab-aware**: Pauses WS connection when browser tab is hidden
- **Dark/light theme**: Toggle button, persisted in `localStorage`
- **Site selector**: Dropdown for multi-site support, updates all data on change
- **Per-client drill-down**: Click a client row for 24h signal/satisfaction charts
- **Historical comparison**: Compare current vs last week (latency, bandwidth, client count)
- **Data export**: Download client or WAN data as CSV or JSON
- **Sortable columns**: Click column headers in client table to sort
- **Chart.js**: Used for WAN latency history, client signal/satisfaction, bandwidth, and comparison overlays

## No Build Step

Plain HTML/CSS/JS -- no bundler, no npm, no transpilation. Served directly by FastAPI's `StaticFiles` mount.

## Dependencies

- [Chart.js](https://www.chartjs.org/) loaded via CDN in `index.html`
- No other external JS dependencies

## Theming

CSS custom properties define all colors. The `[data-theme="dark"]` and `[data-theme="light"]` selectors on `<html>` switch the palette. Chart.js colors are updated dynamically when the theme toggles.
