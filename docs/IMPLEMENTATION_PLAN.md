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

## Phase 2 — Backend foundation
1. Create FastAPI app.
2. Add Pydantic schemas matching `BACKEND_CONTRACT.md`.
3. Implement recommendation domain function with unit tests.
4. Add SQLAlchemy/SQLModel models or simple repository abstraction.
5. Start with SQLite locally; PostgreSQL for deployed persistent history.
6. Add `/v1/problems` and `/v1/problems/{slug}`.
7. Seed the six problem definitions from versioned YAML/JSON files.

## Phase 3 — Benchmark runner
Create a runner interface:
```python
class BenchmarkMethod(Protocol):
    def setup(self, config): ...
    def predict(self, examples): ...
    def metadata(self) -> dict: ...
```

Each task gets deterministic evaluation logic. The runner writes immutable run metadata and raw outputs before aggregation.

First measured benchmark to implement: **Support Ticket Routing** because it is cheap and demonstrates rules vs traditional ML vs LLM clearly.

Suggested methods:
- keyword routing rules
- TF-IDF + Logistic Regression
- small local classifier/transformer
- frontier LLM classification prompt

## Phase 4 — Document benchmark
Second measured benchmark: **Invoice Field Extraction**.
- native PDF text extraction when available
- PaddleOCR/PaddleOCR-VL fallback for image/scanned inputs
- deterministic parsing baseline
- traditional ML/layout baseline if justified
- small VLM
- frontier multimodal LLM

## Phase 5 — Frontend/API integration
- Replace local `assets/data.js` with `/v1` fetches.
- Keep local demo fallback for offline portfolio viewing.
- Backend recommendation becomes authoritative.
- Add run provenance drawer.

## Phase 6 — Public portfolio release
- Vercel frontend
- backend on Render/Railway/Fly.io or compatible service
- Postgres managed database
- rate limits
- public benchmark results read-only
- GitHub Actions CI
- README with architecture and measured findings

## Phase 7 — Expansion
Only after the first two benchmarks are genuinely measured:
- add duplicate detection
- add form validation
- add receipt extraction
- add sentiment classification
- publish methodology/version changelog
