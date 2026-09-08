# Does the job actually need AI?

SimplyWins is a technology decision aid from an AI strategy project. State the
outcome, what happens today, available inputs and a known procedure. A published
rubric suggests the simplest starting approach and what to test. Its output is
ASSESSED, not a measured guarantee or a business investment approval.

| Job | Starting approach |
| --- | --- |
| Deliver an approved pass/fail result | Event, condition, approved template and delivery queue |
| Retrieve a status by exact order ID | Database lookup, with an explicit not-found case |
| Apply a stated formula | Ordinary code or a spreadsheet, with boundary tests |
| Draft novel essay feedback | An AI experiment candidate, with teacher review |

A workflow can combine these steps. Using AI for interpretation does not make
notifications or record retrieval AI tasks. Keeping an existing working process
is a baseline to beat. The app assesses the workflow; it does not execute it.

## What changed

Explicit notification, template, lookup and calculation choices prevent prose
output or missing training labels alone from pushing a task toward an LLM.
Editable examples work without a provider key. Each assessment explains a
simpler alternative, assumptions, and baseline validation. Optional AI-assisted
intake fills the same correctable profile and can still misread a description.

Spam and sentiment benchmarks remain supporting classification experiments.
Their scores cannot validate email delivery or establish that a visitor needs AI.
See [benchmark evidence](BENCHMARKS.md) for the completed matched comparisons.

## Research and open-source review

- [Google Rules of ML](https://developers.google.com/machine-learning/guides/rules-of-ml/) motivates starting with a simple baseline.
- [RAND's AI project study](https://www.rand.org/pubs/research_reports/RRA2680-1.html) motivates understanding the problem, data and workflow before choosing technology.
- [Hidden Technical Debt in ML Systems](https://proceedings.neurips.cc/paper_files/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html) motivates examining system maintenance beyond inference charges.
- [Microsoft Human-AI Interaction guidance](https://www.microsoft.com/en-us/research/articles/guidelines-for-human-ai-interaction-eighteen-best-practices-for-human-centered-ai-design/) informs visible limits and correction paths.
- [JsonLogic](https://github.com/jwadhams/json-logic-js), MIT, was independently exercised for a notification condition. [GoRules ZEN](https://github.com/gorules/zen), MIT core, was reviewed as a decision-table candidate. Neither is advertised as an integrated workflow executor.

Course readings and meeting summaries informed the purpose. Private course
materials are not distributed here. Research informs the design; it does not
validate our rubric's thresholds or another organization's workflow.

## What was tested

Local CI and authored regression cases cover conventional procedures, missing
labels, contradictory interpretation needs, format-check versus generation,
and invariance to irrelevant names. The real key-free API and browser flow were
checked on desktop and mobile, including ASSESSED labels and no unrelated
benchmark attached.

Real Groq mapping checks exposed an exact-identifier shape error that was
corrected. Subsequent checks returned the expected lookup and feedback
candidates; the notification returned conventional automation. Provider errors
also occurred. These are smoke checks, not a measured reliability rate.

The independent JsonLogic example checked approved, failed, missing, draft,
duplicate, unverified-contact and incorrect-type inputs without sending a
message. These authored cases are functional tests, not a measured corpus.

Next: independent domain reviewers and held-out workflow examples, ambiguous
hybrid tasks, false AI recommendations, missed useful AI opportunities, actual
integration and review costs, and production account verification. Rules can
encode unfair policy; no demographic fairness certification is claimed.
See [release limitations](STATUS.md).
