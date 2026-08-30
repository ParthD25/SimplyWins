# QA Checklist

## Product
- [ ] Winner follows the documented decision rule.
- [ ] No method passing all hard requirements is skipped for a more complex model.
- [ ] No winner is forced when none pass.
- [ ] Demo, measured, and estimated results are visibly distinct.

## Frontend
- [ ] Home links work.
- [ ] Library filtering/search works.
- [ ] Every benchmark URL loads.
- [ ] All sliders update the visible recommendation.
- [ ] Auditability toggle changes eligible methods.
- [ ] Cost updates with monthly volume.
- [ ] Chart and table agree.
- [ ] Chart data remains available in table form.
- [ ] Keyboard focus reaches navigation, controls, and chart points.
- [ ] Mobile width has no page-level horizontal overflow except intentional data-table/chart scrolling.

## Backend
- [ ] Schemas validated.
- [ ] Recommendation unit tests cover tie breaks and no-pass state.
- [ ] Run metadata includes provenance requirements.
- [ ] Raw outputs are retained or checksum-addressed.
- [ ] API errors use standard envelope.

## Benchmark integrity
- [ ] Same dataset version used across competing methods.
- [ ] Same evaluation metric definition used across methods.
- [ ] Cost assumptions dated and sourced.
- [ ] Latency methodology documented.
- [ ] Random seeds recorded.
- [ ] Dataset license reviewed.
