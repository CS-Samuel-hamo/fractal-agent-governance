# v0.3.12 Implementation Delivery Kernel

This release upgrades the Zoo Code Agent Governance Kit from governance-only
planning toward implementation delivery.

## Highlights

- `/agent-run` remains the main workflow bus, but implementation tasks now have
  to move toward code, test, config, or execution evidence.
- `/implement` provides an explicit shortcut for turning plans, branch states,
  or task-board items into an implementation queue and Codex task packs.
- New implementation queue artifacts record ready code/test/config work,
  blocked items, follow-up work, allowed files, tests, and root-goal alignment.
- Codex task packs can now be generated from ready implementation queue items.
- Code delivery gates reject coding tasks that finish with docs-only output
  without an explicit no-code blocker.
- Progress snapshots, task boards, and the VS Code/Cursor launcher now surface
  delivery mode, implementation queue status, Codex task packs, blocked items,
  and code delivery gate results.

## Safety Boundary

This release does not loosen high-risk gates. The following still require
separate explicit authorization and review:

- secret reads and `.env` reads
- provider probes and external data updates
- cache mutation and runtime data mutation
- dependency install/rebuild or native repair
- merge, push, deploy, release
- destructive cleanup and production data migration

## Validation

Before publishing, run:

```powershell
python scripts/validate-open-source-package.py
python packages/zoo-code/scripts/validate-zoo-agent-kit.py
python packages/zoo-code/scripts/smoke-test-implementation-delivery.py
```

Then create the release archive from `packages/zoo-code/`.
