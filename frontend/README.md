# Frontend

This is a dependency-free static frontend intentionally built so the product can be reviewed and deployed before the benchmark backend exists.

## Files
- `index.html` — home/product thesis
- `benchmarks.html` — library search/filter
- `benchmark.html?problem=<slug>` — interactive benchmark detail
- `methodology.html` — benchmark standard
- `assets/data.js` — demo problem data
- `assets/app.js` — recommendation logic, chart rendering, interactions
- `assets/styles.css` — complete design system/responsive styling

## Run
```bash
python -m http.server 8000
```
Open `http://localhost:8000`.

## Backend integration
When the FastAPI service is ready:
1. Keep the current local data as a demo/offline fallback.
2. Add an API adapter module rather than calling `fetch` throughout the UI.
3. Map backend `snake_case` payloads to the current frontend problem shape in one place.
4. Treat backend recommendation results as authoritative for published measured benchmarks.
5. Keep instant local recommendation only as a UX preview when the user adjusts constraints.

Do not change visible metric definitions without updating `../PROJECT_STANDARD.md`.

## Connecting to the backend

The site works with no backend: it falls back to the bundled `assets/data.js`
so the static deployment renders on its own. To point it at a running API, set
the base URL before the module scripts load:

```html
<script>window.SIMPLESTWINS_API_BASE = 'https://api.example.com';</script>
```

When the backend answers, it is authoritative — it owns the seed and the
decision rule. When it is configured but unreachable, or not configured at all,
the page says so in a visible note rather than silently showing bundled numbers
as though they came from the service.

The backend must allow the site's origin; set `SIMPLESTWINS_CORS_ORIGINS` on
the API to a comma-separated list.
