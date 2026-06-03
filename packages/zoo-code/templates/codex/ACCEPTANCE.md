# Acceptance Gates

Before completion:

1. Run `git status`.
2. Run `git diff --name-only`.
3. Verify no files outside the assigned task scope were modified.
4. Verify no denied files were modified.
5. List relevant tests for the external harness.
6. Mark scope guard as `harness pending`; the external harness runs `check_codex_scope.py` after Codex exits.
7. Update `PROGRESS.md` with changed files and harness-pending checks.
8. Update `BLOCKERS.md` if blocked.
9. Do not commit, push, merge, reset, or delete branches unless explicitly requested.
