# SimplestWins

**Does this actually need AI?**

SimplestWins benchmarks multiple technical approaches to a task and recommends the least-complex method that still satisfies the real operating requirements.

## What is already built
The `frontend/` directory is a complete dependency-free frontend prototype that can be hosted directly on Vercel or any static host.

Pages:
- `index.html` — product thesis and overview
- `benchmarks.html` — searchable/filterable benchmark library
- `benchmark.html?problem=...` — interactive benchmark explorer
- `methodology.html` — decision standard

The benchmark detail page lets the user change:
- minimum accuracy
- maximum latency
- monthly volume
- auditability requirement

The recommendation, cost projection, scatterplot, and pass/fail table update immediately.

## Run locally
From the project root:
```bash
python -m http.server 8000 -d frontend
```
Then open `http://localhost:8000`.

No package install is required for the frontend.

## Deploy frontend on Vercel
Use `frontend/` as the project root and choose a static deployment/no framework preset. No build command is required.

## Important
All current benchmark numbers are **demo data**. Do not present them as measured results. The project standard requires measured results to include provenance, versions, dataset hashes, and reproducible run metadata.

## Before backend work
Read `PROJECT_STANDARD.md`. It is intentionally strict so Claude Code, Kimi, Codex, or another coding agent does not improvise incompatible architecture or metrics.
