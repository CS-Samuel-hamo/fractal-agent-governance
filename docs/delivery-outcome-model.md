# Delivery Outcome Model

The local alpha separates process execution from usable delivery.

Outcomes:

- `executed`: the worker process ran, but the task did not require delivery proof.
- `delivered`: a business-relevant diff exists and scope/test policy accepted it.
- `no_delivery`: the worker finished but produced no accepted business diff and no valid no-op evidence.
- `no_op_with_evidence`: no diff was needed, and the final evidence names the checked files and the reason.
- `blocked`: execution stopped because the request, files, tests, or worker state could not support delivery.
- `unsafe`: scope guard failed or denied files were touched.

Runtime evidence is not business delivery. Changes under `.zoo-agent/**`, cache files, `__pycache__`,
`.pytest_cache`, and `*.pyc` do not count as a business diff.

As of `0.4.2-delivery-baseline-hardening`, delivery is measured against a task execution baseline:

- `capture_task_baseline.py` records the worktree status before Codex/fast worker execution.
- `compare_task_baseline.py` compares post-execution state to that baseline.
- `check_delivery_outcome.py` uses `task-delta.business_candidate_files` as the source of truth for task delivery.
- Existing bootstrap/governance changes such as `AGENTS.md`, `AGENTS.md.new`, `.gitignore.agent.patch`,
  `.roo/rules/**`, and `.zoo-agent/**` are not counted as coding/docs delivery when they existed before the
  task started.

For docs-only tasks, README or docs changes can be delivered with tests marked `not_applicable`.
For coding tasks, delivery normally requires code or test diff unless the worker provides no-op evidence.

Primary artifacts:

- `.zoo-agent/runs/<run-id>/tasks/<task-id>/task-baseline.json`
- `.zoo-agent/runs/<run-id>/tasks/<task-id>/task-delta.json`
- `.zoo-agent/runs/<run-id>/delivery-outcome.json`
- `.zoo-agent/runs/<run-id>/delivery-outcome.md`
