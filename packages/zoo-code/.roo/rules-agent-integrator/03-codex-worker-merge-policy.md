# Codex Worker Merge Policy

Integrator decisions must use run evidence.

Merge candidates require:

- scope guard pass
- relevant tests pass or explicit accepted deferral
- changed files within task scope
- the final result remains consistent with the original user task objective
- worker execution actually landed, or the run is explicitly governance-only
- no unresolved blockers
- review of `ai-native-summary.json`
- `quality-gate.json` is pass for the claimed action
- `merge-queue.json` is processable, not record-only
- `merge-queue-processing.json` records the serial integrator contract when
  queue processing was authorized
- final reviewer or integration gate authorizes merge readiness
- excluded dirty paths, generated data paths, retired governance paths, secrets,
  and provider profiles remain outside staging and rollback scope
- concurrency conflicts are cleared through `execution_graph.parallel_contract`
  conflict keys when multiple workers or leaves were used
- enough command, environment, and artifact evidence exists for audit or rerun

Level 3 merge decisions require every accepted leaf to have its own evidence. Do not merge a parent workstream solely because the parent artifact exists.

Parallel scheduler merge queues are record-only by default. Treat
`record_only_parallel_candidates_not_processable` as evidence to review, not as
authorization to merge.

Use `run_quality_gate.py --authorize-merge-queue` and then
`process_merge_queue.py --authorize --authorization-note "<why>"` to turn
record-only evidence into a processable serial integration queue. These scripts
do not perform `git merge`, deploy, release, provider probes, data updates,
cache mutation, or durable-state writes.

Read `ai-native-summary.json.governance_state` before merge decisions. Reviewer
or quality evidence is not merge, deploy, release, provider-probe, data-update,
cache-mutation, or durable-state authorization unless the relevant readiness
flag and gate say so.
