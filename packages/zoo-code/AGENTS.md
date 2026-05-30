# Repository Agent Rules

## Mission
This repository is managed by a recursive/fractal multi-agent workflow. Each non-trivial task branch may have its own branch agent; parent agents aggregate child summaries. Agents must preserve project coherence, avoid unbounded recursion, and keep implementation traceable to task contracts.

## Non-Negotiable Execution Rules
1. Do not implement before reading the task contract or creating one if missing.
2. Do not make local-only edits. For every feature or behavior change, inspect and update all required integration surfaces:
   - public interfaces and API contracts
   - route/task/command/branch registration
   - dependency injection and factories
   - enum/constants/type definitions
   - DTO/schema/validator/mapper layers
   - exports and module indexes
   - tests, fixtures, docs, migrations, config, telemetry/logging
3. Before creating new utilities, processors, enums, or helper functions, search for existing equivalents and analogous features.
4. If an existing `Proc*`, `Processor*`, `Handler*`, or service class must be reused with a different data source, explicitly model that data-source difference. Do not silently ignore it.
5. Prefer small, coherent, end-to-end changes over narrow function-only changes.
6. Do not change architecture to satisfy a local task without planner/integrator approval.
7. Every implementation must end with completion evidence: files changed, checks run, acceptance criteria mapping, residual risks.

## Fractal Branch Governance
Each branch node must maintain four artifacts when the task is non-trivial:
- `docs/agent-governance/branch-state/<branch-id>.md`
- `docs/agent-governance/tasks/<task-id>.md`
- `docs/agent-governance/decisions/<decision-id>.md` when architectural decisions are made
- `docs/agent-governance/reviews/<task-id>.review.md` before integration

A branch may create child branches only when splitting reduces complexity, isolates risk, enables parallel work, or clarifies ownership. Each child must have a bounded contract with explicit input, output, acceptance criteria, and merge contract.

## Self-Evolution Rules
The agent governance system may evolve only through the `agent-curator` process:
1. Record an event or postmortem first.
2. Classify the failure.
3. Propose the smallest governance patch.
4. Add a regression prompt/check.
5. Run governance validation.
6. Route the change through reviewer/integrator if it affects team-level workflow.

Execution agents must not rewrite governance rules after their own failure.

## Required Search Before Edit
Use repository search before editing:
- feature name and analogous feature names
- interface names and exports
- enum/constants related to the domain
- registration/routing/task branch files
- existing `Proc*`, `Processor*`, `Handler*`, service, repository, factory, adapter classes
- tests covering the analogous feature

## Verification Gates
Minimum gates for any implementation:
1. Static diagnostics or typecheck if available.
2. Targeted unit/integration tests for changed behavior.
3. Search-based verification that all integration surfaces are updated.
4. Reviewer mode approval before merge.

## Output Contract
Every agent response for non-trivial changes must include:
- `Intent`: target behavior in one paragraph
- `Impact Map`: files/surfaces touched and intentionally untouched
- `Implementation Evidence`: diff summary and rationale
- `Checks`: commands run and results
- `Acceptance Mapping`: requirement -> evidence
- `Risks / Follow-ups`: unresolved issues or explicit none
