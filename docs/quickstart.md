# Quickstart

1. Review the repository safety policy.
2. Inspect `packages/zoo-code/`.
3. Run `python scripts/validate-open-source-package.py`.
4. Run the Zoo Code package validator:
   `python packages/zoo-code/scripts/validate-zoo-agent-kit.py`.
5. Install the adapter globally only after local review, starting with dry-run behavior.
6. Reload VS Code / Zoo Code.
7. Open a toy project first.
8. Bootstrap the project:
   `python <global-kit>/scripts/bootstrap_project.py --project . --mode auto --apply`.
9. Review `.zoo-agent/bootstrap-report.md` and `.zoo-agent/TASKS.md`.
10. Use `/agent-run` for governed execution.

For Codex worker trials, generate a bounded task pack and use dry-run first:

```powershell
python <global-kit>/scripts/run-codex-worker.py --task-dir "<task-dir>" --workspace "<worktree>" --dry-run
```
