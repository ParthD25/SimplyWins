# Backend Workspace

This folder is intentionally a scaffold so backend work can proceed without changing the frontend contract.

Recommended stack:
- Python 3.12+
- FastAPI
- Pydantic v2
- pytest
- SQLAlchemy/SQLModel
- SQLite locally, PostgreSQL when deployed

Start by reading, in order:
1. `../PROJECT_STANDARD.md`
2. `../docs/BACKEND_CONTRACT.md`
3. `../docs/DATA_MODEL.md`
4. `../docs/IMPLEMENTATION_PLAN.md`
5. `../docs/QA_CHECKLIST.md`

Suggested initial structure:
```
backend/
  app/
    main.py
    api/
    domain/
    models/
    repositories/
    schemas/
    services/
    benchmarks/
  tests/
  pyproject.toml
```

Do not connect a model API until the recommendation logic and first deterministic baseline are tested.
