# Ready-to-Use Backend Build Prompt for Claude Code / Kimi / Codex

Copy the prompt below into the coding agent from the **root of this repository**.

---

You are implementing the backend for the existing SimplyWins project. Do not redesign the product and do not rewrite the frontend.

## Read before coding
Read these files completely and treat them as binding requirements:
1. `PROJECT_STANDARD.md`
2. `docs/PRODUCT_SPEC.md`
3. `docs/BACKEND_CONTRACT.md`
4. `docs/DATA_MODEL.md`
5. `docs/IMPLEMENTATION_PLAN.md`
6. `docs/QA_CHECKLIST.md`
7. `frontend/assets/data.js`

If two documents conflict, stop and report the conflict before implementing.

## Goal for this implementation
Build **Phase 2 only: Backend Foundation**.
Do not add model-provider APIs yet.
Do not build the full benchmark runner yet.

## Required stack
- Python 3.12+
- FastAPI
- Pydantic v2
- pytest
- SQLAlchemy 2.x or SQLModel; choose one and document why
- SQLite for local development
- structured logging using Python logging

## Required architecture
Create:
```
backend/
  app/
    main.py
    config.py
    api/
      v1/
        problems.py
        recommendations.py
    domain/
      recommendation.py
    models/
    schemas/
    repositories/
    services/
    seed/
  tests/
    unit/
    integration/
  pyproject.toml
  README.md
```

Rules:
- Route handlers must not contain business logic.
- Recommendation logic must be a pure function in `domain/recommendation.py`.
- Persistence must be accessed through repository interfaces.
- API payloads use snake_case.
- All API schemas are typed.
- No API key or secret is needed in this phase.

## Endpoints required
Implement:
- `GET /health`
- `GET /v1/problems`
- `GET /v1/problems/{slug}`
- `POST /v1/problems/{slug}/recommend`

Use the six existing demo problem definitions from `frontend/assets/data.js` as seed data, but migrate them into backend-owned versioned seed files. The backend becomes the future source of truth.

## Recommendation behavior
Follow `PROJECT_STANDARD.md` exactly:
1. filter methods that pass every hard requirement
2. among passing methods choose lowest complexity_rank
3. tie break on cost then latency
4. if none pass return a clear NO_PASSING_METHOD status; never force a winner

## Tests required before stopping
At minimum:
- rules method wins when it is the simplest passing method
- traditional ML wins when rules fail accuracy
- small model wins when simpler methods fail
- auditability requirement excludes non-auditable methods
- latency ceiling excludes slow methods
- tie break chooses lower cost, then latency
- impossible requirements return NO_PASSING_METHOD
- GET problem endpoints match documented response schema
- unknown slug returns standardized error envelope

## Documentation required
Update `backend/README.md` with:
- install command
- run command
- test command
- architecture summary
- database choice rationale
- how seed data is loaded
- next phase boundary

Add a short implementation record to `CHANGELOG.md`.

## Quality gate
Before you say the work is complete:
- run tests
- run lint/type checks you configure
- start FastAPI and verify all four endpoints
- make sure no frontend files were unintentionally changed
- compare API shapes to `docs/BACKEND_CONTRACT.md`
- list any deliberate deviations; ideally there are none

Do not start Phase 3 or connect any LLM API without explicit approval.

---
