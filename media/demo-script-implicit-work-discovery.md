# Demo Script: Implicit Work Discovery

## Target Audience

AI coding tool builders, agent framework maintainers, and engineering leads evaluating governance around code generation.

## 2 Minute Version

1. Open `examples/implicit-work-discovery/input-task.md`.
2. Read the single-line request: add `blockedReason`.
3. Open `before.md` and show the literal field-only implementation.
4. Open `expected-obligation-ledger.json`.
5. Highlight required, maybe, not_applicable, deferred, and escalated statuses.

Core line:

The runtime turns a small code request into an inspectable propagation ledger.

## 5 Minute Version

1. Start with the problem: agents often complete the literal task and miss integration surfaces.
2. Show `before.md` and name the missed surfaces.
3. Walk through `expected-obligation-ledger.json`.
4. Show `after.md` and explain how each item is closed, deferred, or escalated.
5. Connect the demo to review quality: reviewers can inspect the ledger instead of guessing what the agent considered.

## Files To Show

- `examples/implicit-work-discovery/input-task.md`
- `examples/implicit-work-discovery/before.md`
- `examples/implicit-work-discovery/expected-obligation-ledger.json`
- `examples/implicit-work-discovery/after.md`

## Core Innovation To Emphasize

- Obligation Ledger captures implicit work.
- Status classification prevents vague "done" claims.
- Escalation separates missing information from implementation failure.

## Call To Action

Try the eval case `evals/implicit-work-discovery/cases/add-field.yaml` and compare your agent's output with the expected obligations.
