# Codex Worker Stability on Windows

Version 0.4.3 routes all actual `codex exec` calls through `scripts/codex_exec_adapter.py`.

The adapter is intentionally narrow:

- launches `codex exec` with `subprocess.Popen`, not `shell=True`
- captures stdout and stderr into separate UTF-8 logs with `errors=replace`
- writes a structured `codex-worker-status.json`
- distinguishes total timeout from no-output timeout
- preserves `codex-final-message.md` as the last-message artifact

## Worker Status

`codex-worker-status.json` uses these statuses:

- `succeeded`: process returned `0`
- `failed`: process returned non-zero
- `timeout`: total timeout exceeded
- `no_output_timeout`: no stdout/stderr activity exceeded the configured window
- `spawn_failed`: executable, workspace, or prompt could not be launched
- `exception`: adapter failed unexpectedly
- `dry_run`: command was described but not executed

## Delivery Boundary

Worker execution and task delivery are separate:

- worker failed or timed out -> `delivery_outcome=blocked`
- worker returned `0` with no task baseline business diff -> `delivery_outcome=no_delivery`
- worker returned `0` with accepted README/docs/code/test diff -> `delivery_outcome=delivered`
- worker returned `0` with explicit checked-file no-op evidence -> `delivery_outcome=no_op_with_evidence`

Bootstrap, governance, runtime, cache, and pre-existing baseline diffs are not counted as fast task delivery.

## Health Check

Run:

```powershell
agent codex-health
```

Actual fast execution requires a recent `HEALTHY` or `HEALTHY_WITH_WARNINGS` health report unless explicitly bypassed with `--skip-health-check`.
