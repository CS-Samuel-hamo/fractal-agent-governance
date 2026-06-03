---
description: Run first-run governance intake or a coding task through the v0.3.9 Codex CLI Worker Bridge + Adaptive Fast Path pipeline.
argument-hint: <first-run governance intake | requirement or task id>
mode: agent-orchestrator
---

Run this request through Zoo Code Agent Governance Kit v0.3.9 Codex CLI Worker Bridge + Adaptive Fast Path:

`$ARGUMENTS`

First-run governance intake is read-only. Do not modify production code, run destructive commands, read secrets, or enter coding unless the user clearly requested a coding task.

Project Bootstrap entry checks:

1. If the project has no `.zoo-agent/project-profile.json`, recommend `/agent-bootstrap` or Agent: Bootstrap Project before coding. Do not enter coding unless the user explicitly asks for a quick one-off.
2. If `.zoo-agent/project-readiness.json` exists and `safe_for_level_0_1_trial=false`, do not use the Codex Worker fast path. Report `blocking_issues` first.
3. If `AGENTS.md` is missing, Level 0/1 may continue with a warning, but Level 2+ must generate or confirm project-local rules first.
4. If test command is unknown, Level 0 may continue, Level 1 may continue with warning, and Level 2+ requires GPT planner decision.
5. If `CODEX_HOME` does not exist or Codex CLI is unavailable, do not select Codex Worker; choose DeepSeek/GPT/Zoo-only routing instead.

Before continuing an existing run, read run-ledger state:

1. Detect latest/current run.
2. Read `run-ledger.json`.
3. If `current_state in paused/progress_snapshot`, require `/progress` or Agent: Show Progress and do not continue the old plan.
4. If `.zoo-agent/TASKS.md` or `runs/<run-id>/TASKS.md` is newer than `task-board.json`, require Apply Task Board and stop.
5. If `redirect-plan.json` is newer than `branch-state.json`, apply redirect-plan or stop if invalid transitions exist.
6. If `current_state in redirected/replanning/resume_safety_check`, run `scripts/resume-safety-check.py`; continue only when it writes `resume_ready`.
7. If `merge-queue.json` contains abandoned/redo_needed/paused branches, stop and require `update-merge-queue.py` or resume safety remediation.
8. If `resource-locks.json` has conflicts, stop and require Planner/Orchestrator decision.
9. If parent aggregation is missing but merge queue is non-empty, stop and run `parent-aggregation-gate.py`.

- If `current_state = redirected` or `current_state = replanning`, read `redirect-plan.json` first and adjust goal, branch-state, worktree-map, resource-locks, and merge-queue from that plan. Do not continue the old plan silently.
- If branch status is `abandoned`, do not continue that branch.
- If branch status is `retained`, reuse evidence where valid.
- If branch status is `redo_needed`, replan or re-execute that branch.
- If branch status is `needs_user_decision`, ask the user for a short decision; do not guess.
- If redirect lowers Level 3 work to Level 1, stop default fractal decomposition and use mini obligation check, targeted test, and mechanical review.
- If redirect stops parallel work, do not create new parallel groups; mark existing worktrees `paused` and merge queue `reorder_required`.
- Treat `.zoo-agent/TASKS.md` as the project-level human-editable task board entry for the current run.
- Treat `.zoo-agent/runs/<run-id>/TASKS.md` as the current run's task board archive.
- If either task board is newer than `task-board.json`, `branch-state.json`, or `redirect-plan.json`, apply it with `scripts/apply-task-board.py` before continuing.
- Treat `task-board.json` as the structured scheduler projection. Do not ask users to manually edit `run-ledger.json`, `merge-queue.json`, or `worktree-map.json`.

## Runtime Backbone
`/agent-run` is the only main workflow bus. All governance lines attach to:

`Goal -> Run -> Project Context -> Obligations -> Branch Tree -> Worktree Schedule -> Execution -> Evidence -> Gates -> Review -> Parent Aggregation -> Merge Queue -> Integration -> Metrics -> Lessons`

Unique sources of truth:
- goal-contract: target facts
- run-ledger: process facts
- project-charter: durable project mission, non-goals, quality bar, and human gates
- project-profile: project facts
- project-map: module, file, entrypoint, test, doc, and dependency facts
- architecture-boundaries: dependency direction and module layer facts
- obligation-ledger: implicit work facts
- branch-state: fractal facts
- TASKS.md: project/current-run human task board facts
- worktree-map: worktree/git branch facts
- path-locks: file ownership facts
- resource-locks: path and semantic resource ownership facts
- quality-gate: quality facts
- diagnostics-report: IDE diagnostics facts
- review-report: review facts
- parent-aggregation: parent branch aggregation facts
- merge-queue: integration queue facts
- artifact-graph: artifact version facts
- metrics: outcome facts
- lesson-store: learning facts

## Zoo Boomerang + Fractal Boundary
Zoo Code Boomerang Tasks provide subtask delegation, isolated subtask context, parent pause/resume, child summary return, and specialized mode selection.

Fractal Task Governance runs above Boomerang: recursive decomposition, branch contracts, `needs_decomposition`, max_depth, loop_budget, owned_paths/shared_paths/forbidden_paths, provides/consumes, dependency graph, worktree scheduling, path locks, parent aggregation, merge queue, fallback ladder, and lesson loop.

Simple tasks do not split and must record no-split rationale. Complex tasks create a root branch. A child that is still complex returns `needs_decomposition`; Planner decides whether to split deeper, escalate, fallback, or abort.

## AI-Native Adaptive Main Flow
Do not copy human software-team ceremony step-for-step. Code generation and sandbox exploration are cheap; integration judgment, verification, architecture, security/data, release, and long-term maintenance remain expensive.

1. Init run-ledger.
2. Bind or create goal contract.
3. Ensure or bind project-charter for non-trivial work. Run `scripts/check-project-charter.py`; if missing, first-run intake may draft it with `scripts/init-project-charter.py`, but coding requires a charter or explicit `charter_unknown` escalation.
4. Ensure project-profile, including `codebase_indexing_status` when known.
5. Ensure project-map and architecture-boundaries for non-trivial work. Run `scripts/generate-project-map.py` when missing or stale, and `scripts/check-project-map.py` before multi-module, public API, DTO/schema, Proc/data-source, security/auth/payment/PII/migration, or architecture-boundary work.
4. Classify governance intensity with `classify-governance-intensity.py` and task complexity with `scripts/classify-task-complexity.py`.
5. Select executor with `scripts/select-executor.py`; write `.zoo-agent/runs/<run-id>/executor-selection.json`.
6. Run triggered gate detection with `check-triggered-gates.py`.
7. Check fast path eligibility with `scripts/check-fast-path-eligibility.py`.
8. Generate mini/full obligation ledger depending on level; Level 1+ does mini obligation check and Level 2+ generates full obligation ledger with `discovery_method`.
9. Choose the execution path by level:
   - Level 0 Micro Edit:
     - adaptive fast path
     - optional Codex Task Pack or DeepSeek execution
     - micro execution
     - scope guard
     - diff summary
     - optional diagnostics
     - no full goal/fractal/review unless a trigger appears
   - Level 1 Routine Coding:
     - mini obligation check
     - generate Codex Task Pack unless DeepSeek is explicitly selected
     - run Codex CLI when user or automation policy allows
     - targeted test
     - scope guard
     - diagnostics check
     - mechanical review
   - Level 2 Multi-surface Feature:
     - full obligation ledger
     - Planner may use a low-risk draft path
     - GPT planner approval
     - bounded Codex Task Pack when Codex CLI is selected
     - Codex execution
     - collect result
     - quality gate
     - mechanical review
     - GPT reviewer
   - Level 3 Fractal Workstream:
     - root branch
     - fractal recursive decomposition
     - decide sequential vs worktree parallel
     - branch schedule
     - worktree-map
     - Codex Task Pack per executable leaf branch
     - child execution
     - collect results
     - reconciliation
     - child review
     - parent aggregation
     - merge queue
     - integration gate
   - Level 4 High-risk / Irreversible Change:
     - full governance
     - GPT final planner
     - ADR/security/release/human gate as triggered
     - rollback plan
     - Codex may only execute explicitly bounded subtasks after approval
     - GPT final decision and explicit human gate where required
10. All levels update run-ledger and artifact-graph when runtime artifacts are created.
11. Record checkpoint refs where available with `record-checkpoint-ref.py`.
12. Collect diagnostics where available with `collect-diagnostics-report.py`; quality gate reads diagnostics-report when present.
13. Use codebase indexing for pattern discovery when available; fallback to `rg`/file search and record discovery method.
14. Use project-map module ownership to draft branch `owned_paths`, `shared_paths`, resource locks, and parent aggregation ownership matrices.
15. For Level 3+ fractal work, Planner/Orchestrator must actively run parallel scheduling after branch contracts exist, using `scripts/generate-resource-locks.py`, `scripts/check-resource-locks.py`, `scripts/generate-branch-schedule.py`, `scripts/check-parallel-branch-safety.py`, or `scripts/schedule-parallel-branches.py`, and generate `.zoo-agent/runs/<run-id>/branch-schedule.json`, `.zoo-agent/runs/<run-id>/worktree-map.json`, `.zoo-agent/runs/<run-id>/path-locks.json`, `.zoo-agent/runs/<run-id>/resource-locks.json`, `.zoo-agent/runs/<run-id>/merge-queue.json`, `.zoo-agent/runs/<run-id>/parent-aggregation-matrices.json`, `.zoo-agent/runs/<run-id>/parallel-metrics.json`, and `.zoo-agent/runs/<run-id>/parallel-execution-report.md`.
16. Parallel exploration may run in sandbox/worktree isolation. Parallel direct integration is forbidden; integration branch is serialized.
17. After every child branch completes, run `scripts/reconcile-branch-completion.py` before parent aggregation. It must compare actual changed file names against path locks, verify required branch artifacts, and move failed branches to `needs_decomposition` or rollback planning.
18. Before final integration of a parent or parallel group, run `scripts/parent-aggregation-gate.py`. Final integration is forbidden unless parent aggregation passes.
19. If reconciliation or parent aggregation fails, run `scripts/rollback-branch-worktree.py` to record checkpoint/worktree rollback plan, block merge queue entry, and return to Planner for re-scope, serialization, fallback, or abort.
20. Run feedback convergence with `check-feedback-convergence.py` after each loop.
21. Failure handling: loop budget remains -> remediate; scope exceeded -> `needs_decomposition`; decomposition possible -> Planner split; max_depth exceeded -> Planner escalation; stalled/regressing -> escalate; fractal cannot solve -> fallback ladder; high-risk unresolved -> human gate or abort.
22. Append metrics and produce final run report.
23. Collect events/postmortems, extract lessons only when learning trigger thresholds are met, and run governance regression before approved governance install.
24. Mark stale lessons, skills, rules, local project rules, or script gates as deprecation candidates when policy thresholds are met.

Fast path skip rules: Level 0 and Level 1 must not trigger full fractal decomposition, multi-role flow, governance curation, eval suite, release readiness, or operational readiness unless a trigger signal appears.

## Mandatory Gates
- Level 0 must block high-risk paths and produce a diff summary.
- Level 1 must run mini obligation check, targeted test when available, and mechanical review.
- Level 2+ must bind `goal_id`.
- Non-trivial coding must bind to project-charter or record `charter_unknown` escalation.
- Level 2+ must generate `.zoo-agent/runs/<run-id>/obligation-ledger.json` before execution.
- Required obligations must be closed, deferred with owner/reason, or escalated with escalation id before Level 2+ integration.
- High or critical risk requires GPT final decision or human gate.
- No branch may continue local optimization after exit condition is satisfied.
- Quality gate pass + obligation closed + no BLOCKER/MAJOR + goal coverage satisfied means move to integration or final report.
- Each run must record `.zoo-agent/runs/<run-id>/skill-invocations.json`.
- No governance asset change may install without lesson/proposal evidence, governance regression, approval, validate, dry-run, and safe target paths.
- Default branch execution is dependency ordered and sequential.
- Parallel execution requires non-overlapping owned paths, non-conflicting resource-locks, declared shared paths, stable provides/consumes, no high/critical or security/auth/payment/PII/migration risk, independent acceptance/verification, worktree isolation, path-lock/resource-lock pass, and Planner/Orchestrator approval.
- Parallel branches must enter merge queue; they cannot merge directly.
- Worktree runtime requires worktree-map and checkpoint refs before concurrent coding.
- Parent aggregation matrices are required before final integration of any parallel group.
- Branch completion reconciliation is required before parent aggregation.
- Failed reconciliation must block merge queue and produce rollback or redecomposition plan.
- Checkpoint runtime records checkpoint_ref before executor edits when available and before high-risk or multi-file changes.
- Diagnostics integration blocks new Error diagnostics before integration unless GPT reviewer waives.
- Codebase indexing integration must be used for semantic pattern discovery when available.
- Goal contracts must align with project-charter mission, non-goals, quality bar, data/security constraints, human gates, and fallback/abort conditions.
- Project-map coverage is required for multi-module or architecture-sensitive coding unless an explicit `architecture_unknown` escalation is recorded.
- `/eval` is optional and evaluates governance behavior. It is not run automatically at the end of every `/agent-run`.
- Governance intensity routing is mandatory before selecting the execution path.
- Triggered gates policy: ADR/security/release/ops/eval/governance-curation gates run only when their trigger signals exist; once triggered, they become required gates.
- No artifact, no transition: missing goal contract blocks planning; missing project-charter blocks non-trivial coding unless escalated; missing project profile blocks coding; missing project-map blocks multi-module or architecture-sensitive coding; missing obligation ledger blocks Level 2+ execution; missing branch contract blocks child task; missing worktree-map blocks concurrent coding; missing completion evidence blocks review; missing quality gate blocks integration; missing parent aggregation blocks final integration; missing merge-queue blocks merging parallel branches; missing event plus regression blocks rules/skills changes.
- No stale plan, no resume: stale TASKS.md, stale redirect-plan, merge queue with abandoned/redo_needed/paused branches, resource-lock conflict, missing parent aggregation, or failed resume-safety-check blocks `/agent-run`.

## Triggered Gates
- ADR triggers: public API, shared type, new dependency, architecture boundary, migration, Proc/data-source strategy.
- Security triggers: auth, permission, PII, payment, credential, external network, production config.
- Release triggers: public behavior change, migration, feature flag, breaking change.
- Ops triggers: backend/API/job/database/integration, retry, idempotency, logging, metrics, alerting.
- Curator triggers: repeated failure, BLOCKER/MAJOR, same failure type recurrence, rule/skill drift.
- Eval triggers: governance package upgrade, new skill/rule, model routing change, benchmark/demo. Eval is not a default task gate.

## Parallel Exploration vs Integration
- Sandbox/worktree exploration branches may run in parallel when Planner/Orchestrator approves.
- Candidate branches must be compared by goal coverage, risk reduction, unknown reduction, integration cost, rollback ease, and future optionality.
- Integration branch is single-threaded. No parallel branch may merge directly.
- Root/parent aggregation nodes are never leaf execution nodes and must not enter a parallel execution group.

## Control Plane
Other commands are control-plane tools for the run:
- `/goal` generates or binds goal.
- `/status` reads run-ledger and status artifacts.
- `/risk` updates risk-register.
- `/loop` updates loop-state.
- `/escalate` writes escalation.
- `/fallback` writes fallback report.
- `/decision` writes ADR.
- `/release` writes release readiness.
- `/incident` writes incident/postmortem.
- `/eval` is external governance evaluation, not a default task transition.

## Model Routing
DeepSeek V4 Flash may draft profile, low-risk plan, status, risk, obligation discovery, execution, mechanical review, integration summary, and governance-curation drafts. GPT retains Orchestrator, final Planner, final Reviewer, Integrator, architecture/security/release, and governance-change final decisions.

DeepSeek also may draft diagnostics summaries and worktree status. DeepSeek must escalate unknown, unclear, conflict, security, auth, migration, architecture, data-source mismatch, diagnostics regression, and path conflict to GPT. DeepSeek must not finally decide decomposition, parallel scheduling, merge, security, release, human exception, or governance change.

Codex CLI may perform high-speed bounded implementation only from a Codex Task Pack. Codex CLI reads `AGENTS.md`, `TASKS.yaml`, `ACCEPTANCE.md`, and `CODEX_TASK_PROMPT.md`, runs under `codex exec --cd <worktree> --sandbox workspace-write`, produces `PROGRESS.md`, `BLOCKERS.md`, and evidence, and returns results to Zoo scope guard, quality gate, review gate, and merge queue.
