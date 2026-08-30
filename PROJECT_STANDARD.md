# SimplestWins Project Standard

This file is the source of truth for how SimplestWins is built. If implementation and this standard disagree, stop and update one deliberately. Do not let coding agents invent new architecture, naming, metrics, or product behavior without changing this document first.

## 1. Product thesis
SimplestWins answers one question: **what is the lowest-complexity technical approach that satisfies the operating requirements for a task?**

The product is not an LLM leaderboard. It compares implementation classes such as deterministic rules, traditional ML, smaller learned models, and frontier LLMs under the same task, dataset, and constraints.

## 2. Non-goals
- Do not optimize for making AI win.
- Do not declare a winner when no method passes all required constraints.
- Do not mix demo/synthetic results with measured results without visible labeling.
- Do not hide model/provider/version details for measured runs.
- Do not add chat as the primary interface.
- Do not turn the UI into a generic KPI-card dashboard.
- Do not use an LLM to grade a task when a deterministic assertion or labeled target is available.

## 3. Core decision rule
1. Evaluate every method on the same benchmark definition and dataset version.
2. Filter to methods satisfying all hard requirements.
3. Sort passing methods by `complexity_rank` ascending.
4. Break ties by lower cost, then lower latency.
5. If no method passes, return `NO_PASSING_METHOD`; do not force a winner.

Default complexity order:
1. deterministic rules / schema / regex
2. traditional statistical or ML model
3. small/local learned model
4. frontier hosted model

A benchmark may override this order only with an explicit rationale stored in its definition.

## 4. Required benchmark metadata
Every measured benchmark run must save:
- problem slug and benchmark definition version
- dataset name, dataset version/hash, license, and provenance
- code commit SHA
- method ID and implementation version
- method class / complexity rank
- model provider + exact model version when applicable
- prompt/template version when applicable
- runtime environment
- run timestamp in UTC
- random seed when relevant
- sample count
- accuracy/task-success metric definition
- latency measurement method
- cost calculation method and pricing source/date
- raw result artifact location
- pass/fail against each active constraint

## 5. Data states
Every result must be one of:
- `DEMO` — illustrative mock data for UI/product design only
- `MEASURED` — produced by a reproducible benchmark runner
- `ESTIMATED` — derived from a measured value plus a documented assumption

The frontend must visually distinguish these states.

## 6. API contract rules
- API version prefix: `/v1`.
- JSON keys use `snake_case` in backend payloads.
- IDs/slugs are stable and lowercase-kebab-case.
- Breaking schema changes require `/v2`; do not silently mutate `/v1`.
- Error responses use a consistent envelope: `{ "error": { "code": "...", "message": "...", "details": {} } }`.
- Never return unversioned benchmark outputs.

## 7. Frontend rules
- The main comparison is the focal view; avoid equal-weight card grids.
- Requirements must remain visible near the evidence they affect.
- Essential values are visible without hover.
- Charts need a table fallback.
- Color is semantic: green = passing/recommended, amber = caution, red = failure, blue/purple = method identity.
- Meet WCAG AA contrast for text and interactive controls.
- Keyboard users must be able to inspect chart points and all controls.
- Mobile must preserve the same decision, not a reduced marketing-only experience.
- No decorative AI imagery, robot icons, rainbow gradients, or fake metrics.

## 8. Code standards
- One purpose per module/function.
- No magic numbers in benchmark logic; thresholds come from benchmark definitions or config.
- Pure deterministic functions for recommendation logic.
- Separate domain logic from transport/UI code.
- No provider SDK calls directly from route handlers; use adapters/services.
- Use typed schemas for API payloads and persisted data.
- Secrets only through environment variables; never commit keys.
- Prefer explicit names over abbreviations.
- Keep implementation comments focused on why a decision exists, not restating code.

## 9. Testing gates
Before merge/deploy:
- unit tests for recommendation logic and pass/fail constraints
- contract tests for API schemas
- benchmark smoke test on a tiny fixture dataset
- regression tests for measured benchmark outputs when methodology is unchanged
- frontend interaction test for requirement changes and winner recomputation
- responsive checks at desktop and mobile widths
- accessibility pass for labels, keyboard focus, and chart table alternative
- no console errors

## 10. Documentation gates
Every new benchmark requires:
- benchmark README/problem card
- task definition
- dataset provenance/license
- metric definition
- method implementations included
- known limitations
- expected failure modes
- reproducibility command

## 11. Security/privacy
- Never upload private user data to a model provider without explicit consent and documentation.
- Public demo datasets only for the portfolio deployment.
- Uploaded documents, if added later, require retention rules and a privacy notice.
- Treat model prompts and outputs as potentially sensitive.
- Sanitize filenames and uploaded content.
- Rate-limit public run endpoints.

## 12. Definition of done
A feature is done only when:
- acceptance criteria are met
- tests pass
- documentation is updated
- API/data contracts remain valid or are versioned
- desktop/mobile UX is checked
- demo vs measured data is labeled correctly
- no unresolved high-severity TODOs remain

## 13. Change control
Any change to product thesis, recommendation logic, metric definitions, API schema, benchmark provenance requirements, or visual semantics must first update this standard and be noted in `CHANGELOG.md`.
