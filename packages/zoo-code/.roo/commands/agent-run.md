---
description: Run first-run governance intake or a coding task through the v3.7 Fractal + Zoo Native Runtime pipeline.
argument-hint: <first-run governance intake | requirement or task id>
mode: agent-orchestrator
---

Run this request through Zoo Code Agent Governance Kit v3.7 Fractal + Zoo Native Runtime:

`$ARGUMENTS`

First-run governance intake is read-only. Do not modify production code, run destructive commands, read secrets, or enter coding unless the user clearly requested a coding task.

## Runtime Backbone
`/agent-run` is the only main workflow bus. All governance lines attach to:

`Goal -> Run -> Project Context -> Obligations -> Branch Tree -> Worktree Schedule -> Execution -> Evidence -> Gates -> Review -> Parent Aggregation -> Merge Queue -> Integration -> Metrics -> Lessons`

Unique sources of truth:
- goal-contract: target facts
- run-ledger: process facts
- project-profile: project facts
- obligation-ledger: implicit work facts
- branch-state: fractal facts
- worktree-map: worktree/git branch facts
- path-locks: file ownership facts
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

Simple tasks do not split and must record no-split rationale. Complex tasks create a root branch. A child that is still complex returns `needs_decomposition`; GPT branch-manager decides whether to split deeper, escalate, fallback, or abort.

## AI-Native Adaptive Main Flow
Do not copy human software-team ceremony step-for-step. Code generation and sandbox exploration are cheap; integration judgment, verification, architecture, security/data, release, and long-term maintenance remain expensive.

1. Init run-ledger.
2. Bind or create goal contract.
3. Ensure project-profile, including `codebase_indexing_status` when known.
4. Classify governance intensity with `classify-governance-intensity.py`.
5. Run triggered gate detection with `check-triggered-gates.py`.
6. Generate mini/full obligation ledger depending on level; Level 1+ does mini obligation check and Level 2+ generates full obligation ledger with `discovery_method`.
7. Choose the execution path by level:
   - Level 0 Micro Edit:
     - micro execution
     - diff summary
     - optional diagnostics
     - no full goal/fractal/review unless a trigger appears
   - Level 1 Routine Coding:
     - mini obligation check
     - executor
     - targeted test
     - diagnostics check
     - mechanical review
   - Level 2 Multi-surface Feature:
     - full obligation ledger
     - plan-drafter if low risk
     - GPT planner approval
     - executor
     - quality gate
     - mechanical review
     - GPT reviewer
   - Level 3 Fractal Workstream:
     - root branch
     - fractal recursive decomposition
     - decide sequential vs worktree parallel
     - child execution
     - child review
     - parent aggregation
     - merge queue
     - integration gate
   - Level 4 High-risk / Irreversible Change:
     - full governance
     - ADR/security/release/human gate as triggered
     - rollback plan
     - GPT final decision and explicit human gate where required
8. All levels update run-ledger and artifact-graph when runtime artifacts are created.
9. Record checkpoint refs where available with `record-checkpoint-ref.py`.
10. Collect diagnostics where available with `collect-diagnostics-report.py`; quality gate reads diagnostics-report when present.
11. Use codebase indexing for pattern discovery when available; fallback to `rg`/file search and record discovery method.
12. If branches may be parallel, GPT branch-manager/orchestrator must generate `.zoo-agent/runs/<run-id>/branch-schedule.json`, `.zoo-agent/runs/<run-id>/worktree-map.json`, `.zoo-agent/runs/<run-id>/path-locks.json`, and `.zoo-agent/runs/<run-id>/merge-queue.json`.
13. Parallel exploration may run in sandbox/worktree isolation. Parallel direct integration is forbidden; integration branch is serialized.
14. Run feedback convergence with `check-feedback-convergence.py` after each loop.
15. Failure handling: loop budget remains -> remediate; scope exceeded -> `needs_decomposition`; decomposition possible -> branch-manager split; max_depth exceeded -> GPT planner/branch-manager; stalled/regressing -> escalate; fractal cannot solve -> fallback ladder; high-risk unresolved -> human gate or abort.
16. Append metrics and produce final run report.
17. Collect events/postmortems, extract lessons when thresholds are met, and run governance regression before approved governance install.
18. Mark stale lessons, skills, rules, local project rules, or script gates as deprecation candidates when policy thresholds are met.

## Mandatory Gates
- Level 0 must block high-risk paths and produce a diff summary.
- Level 1 must run mini obligation check, targeted test when available, and mechanical review.
- Level 2+ must bind `goal_id`.
- Level 2+ must generate `.zoo-agent/runs/<run-id>/obligation-ledger.json` before execution.
- Required obligations must be closed, deferred with owner/reason, or escalated with escalation id before Level 2+ integration.
- High or critical risk requires GPT final decision or human gate.
- No branch may continue local optimization after exit condition is satisfied.
- Quality gate pass + obligation closed + no BLOCKER/MAJOR + goal coverage satisfied means move to integration or final report.
- Each run must record `.zoo-agent/runs/<run-id>/skill-invocations.json`.
- No governance asset change may install without lesson/proposal evidence, governance regression, approval, validate, dry-run, and safe target paths.
- Default branch execution is dependency ordered and sequential.
- Parallel execution requires non-overlapping owned paths, declared shared paths, stable provides/consumes, no high/critical or security/auth/payment/PII/migration risk, independent acceptance/verification, worktree isolation, path-lock pass, and GPT branch-manager/orchestrator approval.
- Parallel branches must enter merge queue; they cannot merge directly.
- Worktree runtime requires worktree-map before concurrent coding.
- Checkpoint runtime records checkpoint_ref before executor edits when available and before high-risk or multi-file changes.
- Diagnostics integration blocks new Error diagnostics before integration unless GPT reviewer waives.
- Codebase indexing integration must be used for semantic pattern discovery when available.
- `/eval` is optional and evaluates governance behavior. It is not run automatically at the end of every `/agent-run`.
- Governance intensity routing is mandatory before selecting the execution path.
- Triggered gates policy: ADR/security/release/ops/eval/curator gates run only when their trigger signals exist; once triggered, they become required gates.
- No artifact, no transition: missing goal contract blocks planning; missing project profile blocks coding; missing obligation ledger blocks Level 2+ execution; missing branch contract blocks child task; missing worktree-map blocks concurrent coding; missing completion evidence blocks review; missing quality gate blocks integration; missing parent aggregation blocks final integration; missing merge-queue blocks merging parallel branches; missing event plus regression blocks rules/skills changes.

## Triggered Gates
- ADR triggers: public API, shared type, new dependency, architecture boundary, migration, Proc/data-source strategy.
- Security triggers: auth, permission, PII, payment, credential, external network, production config.
- Release triggers: public behavior change, migration, feature flag, breaking change.
- Ops triggers: backend/API/job/database/integration, retry, idempotency, logging, metrics, alerting.
- Curator triggers: repeated failure, BLOCKER/MAJOR, same failure type recurrence, rule/skill drift.
- Eval triggers: governance package upgrade, new skill/rule, model routing change, benchmark/demo. Eval is not a default task gate.

## Parallel Exploration vs Integration
- Sandbox/worktree exploration branches may run in parallel when GPT branch-manager/orchestrator approves.
- Candidate branches must be compared by goal coverage, risk reduction, unknown reduction, integration cost, rollback ease, and future optionality.
- Integration branch is single-threaded. No parallel branch may merge directly.

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
DeepSeek V4 Flash may draft profile, low-risk plan, status, risk, obligation discovery, execution, mechanical review, integration clerk report, and curator drafts. GPT-5.5 retains orchestrator, final planner, branch-manager, final reviewer, integrator, curator, architecture/security/release final decisions.

DeepSeek also may draft diagnostics summaries and worktree status. DeepSeek must escalate unknown, unclear, conflict, security, auth, migration, architecture, data-source mismatch, diagnostics regression, and path conflict to GPT. DeepSeek must not finally decide decomposition, parallel scheduling, merge, security, release, human exception, or governance change.
