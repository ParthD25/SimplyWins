# Implementation Plan

## Phase 0 — Standard + product definition (complete)
- Product thesis
- MVP benchmark list
- Decision rule
- UI design system
- Backend/API contract
- Data model

## Phase 1 — Frontend prototype (complete)
- Home page
- Benchmark library with search/filter
- Interactive benchmark detail page
- Cost-vs-accuracy scatterplot
- Requirements controls
- Detailed method table
- Methodology page
- Mobile navigation and responsive layout
- Clear demo-data labeling

## Phase 2 — Backend foundation (complete)
1. Create FastAPI app.
2. Add Pydantic schemas matching `BACKEND_CONTRACT.md`.
3. Implement recommendation domain function with unit tests.
4. Add SQLAlchemy/SQLModel models or simple repository abstraction.
5. Start with SQLite locally; PostgreSQL for deployed persistent history.
6. Add `/v1/problems` and `/v1/problems/{slug}`.
7. Seed the six problem definitions from versioned YAML/JSON files.

## Phase 3 — Benchmark runner (partly complete)
Create a runner interface:
```python
class BenchmarkMethod(Protocol):
    def setup(self, config): ...
    def predict(self, examples): ...
    def metadata(self) -> dict: ...
```

Each task gets deterministic evaluation logic. The runner writes immutable run metadata and raw outputs before aggregation.

First measured benchmark: **Support Ticket Routing**. Done, with two of four
methods measured:

| Method | Status | Accuracy | p50 |
| --- | --- | --- | --- |
| keyword routing rules | MEASURED | 75.69% | ~0.11ms |
| TF-IDF + logistic regression | MEASURED | 89.50% | ~0.71ms |
| small local classifier | not implemented | — | — |
| frontier LLM prompt | not implemented | — | — |

The last two need a model provider, which is unconnected by choice. Until they
are measured the evidence rule (section 3.1 of `PROJECT_STANDARD.md`) declines
to recommend anything for this problem, and the UI says so.

Worth recording: **neither measured method clears the problem's own 92%
accuracy requirement.** The demo figures claimed 91.7% and 94.6%, i.e. that
both passed. Measuring said otherwise.

## Phase 4 — Document benchmark
Second measured benchmark: **Invoice Field Extraction**.
- native PDF text extraction when available
- PaddleOCR/PaddleOCR-VL fallback for image/scanned inputs
- deterministic parsing baseline
- traditional ML/layout baseline if justified
- small VLM
- frontier multimodal LLM

## Phase 5 — Frontend/API integration (complete)
- `frontend/assets/api.js` fetches from `/v1` when a backend is configured.
- The bundled `data.js` remains the offline fallback, and the page says which
  source it used rather than falling back silently.
- The backend is authoritative when reachable.
- Run provenance reaches the API (`run_id`, dataset checksum, sample count);
  a dedicated drawer for it is still outstanding.

## Phase 6 — Public portfolio release (partly complete)
- Vercel frontend — **live** at https://simply-wins.vercel.app
- GitHub Actions CI — **done**: lint, format, strict types, tests, migration
  drift check, benchmark smoke run, and a browser gate that verifies the
  evidence rule
- Container image and deployment guide — **done** (`backend/Dockerfile`,
  `docs/DEPLOYMENT.md`); not yet built or hosted anywhere
- Backend hosting and managed Postgres — outstanding, needs an account
- Rate limits — outstanding, and required by section 11 before a public API
- README with architecture and measured findings — **done**

## Phase 7 — Expansion
Only after the first two benchmarks are genuinely measured:
- add duplicate detection
- add form validation
- add receipt extraction
- add sentiment classification
- publish methodology/version changelog
