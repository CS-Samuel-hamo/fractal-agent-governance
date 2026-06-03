# Zoo Todo And Agent Task Board Boundary

Zoo native Todo is only a local checklist for the current active child task. It is not the global fractal task tree, not a source for `branch-state.json`, and not a source for `merge-queue.json`.

Agent `TASKS.md` is the whole-run human-editable task board. It expresses root -> parent -> child structure and branch overrides such as `retained`, `abandoned`, `redo_needed`, `paused`, and `needs_user_decision`.

If Zoo native Todo conflicts with `branch-state.json` or `run-ledger.json`, runtime facts win and a consistency warning must be recorded.
