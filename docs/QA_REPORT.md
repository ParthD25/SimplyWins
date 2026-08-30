# Frontend QA Report — v0.1.0

## Visual review
Reference concept and implementation screenshots are stored in `docs/qa/`.

Checked:
- desktop home at 1440 px
- mobile home at 390 px
- desktop benchmark at 1440 px
- mobile benchmark at 390 px

Results:
- no page-level horizontal overflow at desktop or mobile widths
- mobile navigation collapses to a drawer control
- recommendation, requirement controls, chart, table, and evidence sections remain in reading order
- dense table/chart areas use intentional internal scrolling on narrow screens
- text remains inside panels/cards in reviewed states
- dominant comparison remains visually stronger than supporting content
- demo-data status is visible

## Logic checks
Executed JavaScript recommendation logic against all six demo problems.
Expected default winners:
- Invoice Field Extraction -> Rules + OCR
- Messy Receipt Extraction -> Small Model
- Support Ticket Routing -> Traditional ML
- Duplicate Record Detection -> Rules + Fuzzy
- Form Validation -> Rules
- Sentiment Classification -> Small Model

Verified a deliberately impossible requirement set produces the no-passing-method path rather than reporting a false passing winner.

## Remaining QA for backend integration
- real API contract tests
- loading/error/empty states
- benchmark provenance drawer
- public deployment performance audit
- automated browser interaction tests
