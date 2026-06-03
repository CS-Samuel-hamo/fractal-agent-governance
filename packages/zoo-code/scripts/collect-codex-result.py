#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> dict:
    proc = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = proc.stdout if proc.returncode == 0 else proc.stdout + proc.stderr
    return {"returncode": proc.returncode, "output": output}


def read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def update_artifact_graph(run_root: Path, task_id: str, result_json: Path, result_md: Path) -> None:
    graph_path = run_root / "artifact-graph.json"
    if graph_path.exists():
        try:
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
        except Exception:
            graph = {}
    else:
        graph = {}
    artifacts = graph.setdefault("artifacts", [])
    artifacts.append({
        "kind": "codex-result",
        "task_id": task_id,
        "result_json": str(result_json),
        "result_md": str(result_md),
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    })
    graph_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect Codex worker evidence into Zoo result artifacts.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args()

    task_dir = Path(args.task_dir).resolve()
    workspace = Path(args.workspace).resolve()
    run_root = workspace / ".zoo-agent" / "runs" / args.run_id
    out_dir = run_root / "codex-results" / args.task_id
    out_dir.mkdir(parents=True, exist_ok=True)

    status = run(["git", "status", "--short"], workspace)
    diff_names = run(["git", "diff", "--name-only"], workspace)
    diff_stat = run(["git", "diff", "--stat"], workspace)
    final_msg = read_optional(task_dir / "codex-final-message.md")
    progress = read_optional(task_dir / "PROGRESS.md")
    blockers = read_optional(task_dir / "BLOCKERS.md")
    codex_run = json.loads(read_optional(task_dir / "codex-run.json") or "{}")

    scope = {"status": "not_run"}
    guard = task_dir / "check_codex_scope.py"
    tasks = task_dir / "TASKS.yaml"
    if guard.exists() and tasks.exists():
        ignore_result = (Path(".zoo-agent") / "runs" / args.run_id / "codex-results" / args.task_id / "**").as_posix()
        proc = run(
            [
                "python",
                str(guard),
                "--task-id",
                args.task_id,
                "--tasks",
                str(tasks),
                "--json-output",
                str(out_dir / "scope-guard.json"),
                "--ignore-file",
                ignore_result,
            ],
            workspace,
        )
        scope = {"status": "pass" if proc["returncode"] == 0 else "fail", "returncode": proc["returncode"], "output": proc["output"]}

    result = {
        "run_id": args.run_id,
        "task_id": args.task_id,
        "workspace": str(workspace),
        "task_dir": str(task_dir),
        "git_status_short": status,
        "git_diff_name_only": [line for line in diff_names["output"].splitlines() if line.strip()],
        "git_diff_stat": diff_stat,
        "scope_guard": scope,
        "codex_run": codex_run,
        "final_message": final_msg,
        "progress_md": progress,
        "blockers_md": blockers,
        "collected_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    result_json = out_dir / "result.json"
    result_md = out_dir / "result.md"
    result_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result_md.write_text(
        f"""# Codex Result: {args.task_id}

## Scope Guard

{scope.get('status')}

```text
{scope.get('output', '')}
```

## Git Status

```text
{status['output']}
```

## Changed Files

```text
{diff_names['output']}
```

## Diff Stat

```text
{diff_stat['output']}
```

## Codex Final Message

{final_msg}

## Progress

{progress}

## Blockers

{blockers}
""",
        encoding="utf-8",
    )
    update_artifact_graph(run_root, args.task_id, result_json, result_md)
    print(out_dir)
    return 0 if scope.get("status") != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
