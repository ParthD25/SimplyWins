# SimplestWins Project Standard

This file is the source of truth for how SimplestWins is built. If implementation and this standard disagree, stop and update one deliberately. Do not let coding agents invent new architecture, naming, metrics, or product behavior without changing this document first.

## 1. Product thesis
SimplestWins answers one question: **what is the lowest-complexity technical approach that satisfies the operating requirements for a task?**

The product is not an LLM leaderboard. It compares implementation classes such as deterministic rules, traditional ML, smaller learned models, and frontier LLMs under the same task, dataset, and constraints.

## 2. Non-goals
- Do not optimize for making AI win.
- Do not declare a winner when no method passes all required constraints.
- Do not let a `DEMO` or `ESTIMATED` value influence a recommendation (see 3.1).
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

### 3.1 Evidence rule

**No value may influence a SimplestWins recommendation unless its provenance
state is `MEASURED`. A benchmark whose method set mixes provenance states
cannot produce a final recommendation.**

This is the load-bearing rule of the product. SimplestWins exists to answer a
question with evidence; a recommendation shaped even partly by illustrative
numbers is the failure the project is built to prevent.

It follows that:

- `DEMO` and `ESTIMATED` values never enter ranking, tie-breaks, the passing
  set, or the Pareto frontier. They are display-only.
- A recommendation is produced only when **every** method in the benchmark's
  declared method set carries a `MEASURED` result. Until then the status is
  `BENCHMARK_INCOMPLETE` and no winner is named.
- `BENCHMARK_INCOMPLETE` must state how much evidence exists — for example
  "2 of 4 methods measured".
- A "best measured result so far" may be shown, and must not be labelled a
  recommendation. An unmeasured method can still change the outcome, so calling
  a provisional leader a recommendation would overstate what is known.
- Shipping an incomplete benchmark is allowed and expected. Concealing that it
  is incomplete is not.
- `NOT_RUN` marks a method that belongs to the comparison set but has never
  been run. It is distinct from `DEMO`, which carries illustrative figures:
  a `NOT_RUN` method carries none, and its zero fields are placeholders that
  must never be read, rendered, or filtered as values. Read literally they
  describe a method that is instant, free, and perfectly inaccurate, which is
  the most attractive method in any comparison. Such a method is still counted
  in the method total, because the rule above turns on **every** method having
  been measured.

Cost derived from a measured value plus a documented assumption is `ESTIMATED`
(section 5) and therefore cannot break a tie or exclude a method. It may be
displayed alongside the evidence that produced it.

### 3.2 A result is only evidence if the experiment could have failed

**Every measured result must be published alongside the floors it had to beat:
uniform chance, the score for always predicting the most common label, and the
proportion of the evaluation set that also appears in training. A figure
presented without them is not evidence, because a reader cannot tell a result
from an artefact.**

Two further requirements follow, and both exist because this project violated
them and produced a meaningless benchmark as a result:

- **No method may be evaluated on data written by whoever wrote the method.**
  A corpus generated in this repository and a keyword baseline written by the
  same author share a vocabulary, and the benchmark then measures the author
  rather than the method. Measured: 73.6% of that baseline's keywords appeared
  verbatim in the generator's own templates, the shared terms carried the
  entire 78.9% score, and the terms chosen independently scored 25.3% against
  a 20% floor. Benchmark corpora must come from a named external source with
  its licence recorded.
- **A method whose behaviour is defined by a term list must publish that list's
  provenance** — what fraction of its terms occur in the training data, and
  what the attested and unattested halves score separately. A baseline whose
  every term is drawn from the corpus it is graded on is a fitted model, and
  calling it a rules baseline misrepresents the comparison.

A claim about a method's independence from its data is not admissible in a
docstring or a comment. It must be measured on every run and published with the
result, because the claim in this project's own code was false and went
unchallenged for as long as nothing checked it.

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
- `NOT_RUN` — in the comparison set, never run, carrying no figures at all

The frontend must visually distinguish these states. `DEMO` results are
presented as visually separated and muted relative to `MEASURED` results, and
labelled illustrative rather than evidence. `NOT_RUN` results must render no
numbers whatsoever — not a zero, not a dash with a unit, and no point on a
chart — because the absence of a measurement is not a measurement of zero.

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
