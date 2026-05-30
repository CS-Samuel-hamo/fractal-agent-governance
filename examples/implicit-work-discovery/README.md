# Demo 1: Implicit Work Discovery

This demo shows how a small explicit task expands into a governed set of obligations.

Task:

> Add field `blockedReason` to branch summary.

A normal execution model may only add one field to one type. The governed runtime records the propagation surface in an Obligation Ledger: DTO, schema, mapper, API response, UI consumer, fixtures, behavior tests, docs, compatibility, and rollback notes.

Use this demo to compare:

- `before.md`: literal execution that misses propagation.
- `expected-obligation-ledger.json`: governed interpretation of explicit and implicit work.
- `after.md`: completion state after obligations are handled or classified.
- `demo-walkthrough.md`: step-by-step presenter notes.

All files are toy examples. They do not reference a real project, real logs, or secrets.
