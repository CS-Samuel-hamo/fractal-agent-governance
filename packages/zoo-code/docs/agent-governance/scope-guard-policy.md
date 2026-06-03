# Scope Guard Policy

Every Codex task is constrained by `allowed_files` and `denied_files`.

`scripts/check-codex-scope.py` and generated `check_codex_scope.py` must:

- read `TASKS.yaml`
- run `git diff --name-only`
- include staged and untracked files
- fail when changed files are outside `allowed_files`
- fail when changed files match `denied_files`
- output JSON when requested
- print a human-readable report
- exit 1 on violation

Scope guard is a gate, not a suggestion. Zoo must not review or integrate Codex output that fails scope guard unless a higher-authority planner explicitly expands scope and regenerates the Task Pack.
