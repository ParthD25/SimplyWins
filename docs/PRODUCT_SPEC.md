# Product Specification

## Product
**SimplestWins** — a public benchmark and decision tool for determining whether a task needs rules, traditional ML, a smaller model, or a frontier LLM.

## Primary audience
- engineering students and practitioners learning AI system design
- product/engineering teams deciding how much AI a workflow actually needs
- recruiters/interviewers reviewing evidence of AI strategy and systems thinking

## Core user journey
1. User opens the benchmark library.
2. User selects a problem such as invoice extraction or ticket routing.
3. User sees the default operating requirement.
4. User adjusts minimum accuracy, latency ceiling, auditability, and operating volume.
5. Frontend recomputes the simplest method that satisfies all hard constraints.
6. User inspects the cost-vs-quality chart and detailed comparison table.
7. User opens methodology to understand exactly how the recommendation is produced.

## MVP scope
Six benchmark problems:
1. Invoice field extraction
2. Messy receipt extraction
3. Support ticket routing
4. Duplicate record detection
5. Form validation
6. Sentiment classification

Four method classes per problem:
- rules/deterministic
- traditional ML
- small model
- frontier LLM

## Acceptance criteria
- Benchmark library can filter/search problems.
- Benchmark detail page is fully usable on desktop and mobile.
- Requirement controls update recommendation, chart threshold, monthly cost, and table pass/fail state immediately.
- If no method satisfies all constraints, UI says so explicitly.
- Demo results are visibly labeled as demo data.
- Backend can replace mock data without changing the visible UI schema.
