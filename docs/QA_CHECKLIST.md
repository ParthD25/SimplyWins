# QA Checklist

## Product
- [x] Winner follows the documented decision rule.
- [x] No method passing all hard requirements is skipped for a more complex model.
- [x] No winner is forced when none pass.
- [x] Demo, measured, and estimated results are visibly distinct.

## Frontend
- [x] Home links work.
- [x] Library filtering/search works.
- [x] Every benchmark URL loads.
- [x] All sliders update the visible recommendation.
- [x] Auditability toggle changes eligible methods.
- [x] Cost updates with monthly volume.
- [x] Chart and table agree.
- [x] Chart data remains available in table form.
- [x] Keyboard focus reaches navigation, controls, and chart points.
- [x] Mobile width has no page-level horizontal overflow except intentional data-table/chart scrolling.

## Backend
- [x] Schemas validated.
- [x] Recommendation unit tests cover tie breaks and no-pass state.
- [x] Run metadata includes provenance requirements.
- [x] Raw outputs are retained or checksum-addressed.
- [x] API errors use standard envelope.

## Benchmark integrity
- [x] Same dataset version used across competing methods.
- [x] Same evaluation metric definition used across methods.
- [x] Cost assumptions dated and sourced.
- [x] Latency methodology documented.
- [x] Random seeds recorded.
- [x] Dataset license reviewed.

## Enforcement

Most of the above is now checked by CI rather than by hand:

- `backend/tests/` — decision rule, evidence rule, error envelope, run
  provenance, score recomputation from the raw artifact, dataset integrity,
  migration drift (176 tests)
- `ci/render-check.mjs` — five pages at two widths, asserting no console
  errors, no failed requests and no page-level horizontal overflow; then
  exercising the interactions a human used to click through (home links resolve,
  search and category filters narrow the list, every benchmark URL loads,
  sliders change the stated requirements, volume moves the projected cost, the
  auditability toggle changes which methods qualify, chart and table agree on
  method count, the chart's table fallback matches, and keyboard focus reaches
  navigation, controls and chart points); and finally verifying the evidence
  rule in a real browser.

The gate was checked against a deliberately weakened evidence rule and failed
with four errors and a non-zero exit, so it is not passing vacuously.
