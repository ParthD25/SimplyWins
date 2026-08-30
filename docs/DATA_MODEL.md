# Data Model

## Problem
- id UUID
- slug unique string
- title
- category
- description
- decision_question
- benchmark_definition_version
- status
- created_at / updated_at

## DatasetVersion
- id UUID
- problem_id
- name
- version
- sha256
- license
- source_url
- provenance_notes
- sample_count

## Method
- id UUID
- stable_key
- name
- method_class
- complexity_rank
- implementation_version
- provider optional
- model_name optional
- model_version optional

## BenchmarkRun
- id UUID
- problem_id
- dataset_version_id
- method_id
- code_commit_sha
- seed optional
- started_at / completed_at
- environment_json
- prompt_version optional
- state: queued/running/succeeded/failed

## Result
- run_id
- accuracy
- task_success_rate optional
- latency_p50_ms
- latency_p95_ms optional
- cost_per_1k
- deterministic
- auditable
- raw_artifact_uri
- metric_definition_version
- result_state DEMO/MEASURED/ESTIMATED

## RequirementProfile
- id UUID
- problem_id
- name
- min_accuracy
- max_latency_ms
- auditability_required
- monthly_volume
