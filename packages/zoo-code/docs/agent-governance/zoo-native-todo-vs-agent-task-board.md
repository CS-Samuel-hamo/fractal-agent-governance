# Zoo Native Todo Vs Agent Task Board

Zoo native Todo and Agent Task Board have different responsibilities.

## Zoo Native Todo

- Current active child task checklist.
- Local, short-lived execution steps.
- Not the global fractal tree.
- Not a source for `branch-state.json`.
- Not a source for `merge-queue.json`.
- Must not be used to infer whole-run completion.

## Agent `TASKS.md`

- Whole-run human-editable task board.
- Represents root -> parent -> child structure.
- Can express `retained`, `abandoned`, `redo_needed`, `paused`, and `needs_user_decision`.
- Writes back to runtime state only through Apply Task Board.

## Agent Progress Tree

- GUI view of whole-run hierarchy.
- Root and parent nodes are collapsible.
- Active child is highlighted.
- Siblings remain visible but can be collapsed.

If Zoo native Todo conflicts with `branch-state.json` or `run-ledger.json`, runtime facts win and a consistency warning should be recorded.
