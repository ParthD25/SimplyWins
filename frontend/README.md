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
