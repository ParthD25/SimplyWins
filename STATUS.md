# Release status

Verified September 7, 2026.

## Ready to showcase

- The automation-first frontend and API are deployed. Notification and exact-lookup examples return conventional automation; novel-feedback returns an AI experiment candidate. These key-free flows passed live desktop and mobile checks.
- All published prediction artifacts were rechecked; fresh rules and traditional-ML runs reproduced their published accuracy.
- All four benchmark tasks expose four measured methods through the live API.
- Saved predictions reproduce every published aggregate accuracy; evaluation IDs, dataset versions, seeds, and floors were checked.
- Local CI passed: lint, formatting, strict types, migration drift, backend tests, benchmark smoke run, responsive browser checks, and Firestore rules tests.
- The live home, library, comparison, and account pages loaded without JavaScript page exceptions during browser inspection.
- Both Groq comparator models answered a fresh bounded adapter check. This is a connectivity check, not another benchmark measurement.

## Before a full production launch

1. Supply Firebase's public web configuration to the production frontend. Verify sign-in, saving a provider credential, quoting and running a private experiment, reading its result, and deleting the credential from a real browser session.
2. Verify persistent storage, backups and restoration, operational monitoring, and error reporting. Test concurrency; long-running experiments need durable jobs and shared rate limits before scaling beyond the current bounded service.
3. Validate the assessment rubric with independent domain reviewers and held-out workflows, including hybrid tasks and false AI recommendations. Measure actual workflow and review costs. Validate quality on larger, independently held-out and out-of-domain data. Investigate complaint routing's failure to meet the default quality bar. Use protected-group evidence where appropriate before making any demographic fairness claim.
4. Review remaining development-tool dependency advisories and validate each additional provider path before advertising it as supported in production.

The current evidence is useful for demonstrating the decision process. It does not certify reliability, fairness, or accuracy for a visitor's production traffic.
