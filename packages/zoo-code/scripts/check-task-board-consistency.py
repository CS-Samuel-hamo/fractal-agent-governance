#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from task_board_common import branch_state_map, load_json, normalize_status, now, resolve_run_dir, write_json


BAD_QUEUE_STATUSES = {"abandoned", "redo_needed", "paused"}


def newer(left: Path, right: Path) -> bool:
    return left.exists() and (not right.exists() or left.stat().st_mtime > right.stat().st_mtime)


def project_root_for_run(run: Path) -> Path:
    resolved = run.resolve()
    if resolved.parent.name == "runs" and resolved.parent.parent.name == ".zoo-agent":
        return resolved.parent.parent.parent
    return Path.cwd().resolve()


def check(run: Path, run_id: str) -> dict:
    issues = []
    warnings = []
    tasks = run / "TASKS.md"
    board = run / "task-board.json"
    redirect = run / "redirect-plan.json"
    branch_state_path = run / "branch-state.json"
    project_tasks = project_root_for_run(run) / ".zoo-agent" / "TASKS.md"
    if newer(project_tasks, tasks):
        issues.append({"severity": "blocker", "type": "project_task_board_newer_than_run_task_board", "message": ".zoo-agent/TASKS.md has unapplied edits", "fix": "run apply-task-board.py"})
    if newer(tasks, board):
        issues.append({"severity": "blocker", "type": "stale_task_board", "message": "TASKS.md is newer than task-board.json", "fix": "run apply-task-board.py"})
    if newer(tasks, redirect):
        warnings.append({"severity": "warning", "type": "stale_redirect_plan", "message": "TASKS.md is newer than redirect-plan.json"})
    if newer(redirect, branch_state_path):
        issues.append({"severity": "blocker", "type": "redirect_plan_not_applied", "message": "redirect-plan.json is newer than branch-state.json"})
    branch_state = load_json(branch_state_path, {"branches": []})
    status_by_id = {bid: normalize_status(item.get("status")) for bid, item in branch_state_map(branch_state).items()}
    queue = load_json(run / "merge-queue.json", {"queue": []})
    for item in queue.get("queue", []):
        bid = item.get("branch_id")
        status = status_by_id.get(bid)
        if status in BAD_QUEUE_STATUSES:
            issues.append({"severity": "blocker", "type": "merge_queue_references_non_executable_branch", "branch_id": bid, "branch_status": status, "fix": "run update-merge-queue.py or resume-safety-check.py"})
    return {
        "schema_version": "1.1",
        "run_id": run_id,
        "created_at": now(),
        "status": "fail" if issues else "pass",
        "issues": issues,
        "warnings": warnings,
    }


def render_md(report: dict) -> str:
    lines = ["# Task Board Consistency", "", f"- status: `{report['status']}`", ""]
    lines.extend(["## Issues", ""])
    lines.extend([f"- `{json.dumps(x, ensure_ascii=False)}`" for x in report["issues"]] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- `{json.dumps(x, ensure_ascii=False)}`" for x in report["warnings"]] or ["- none"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check TASKS.md/task-board/runtime state consistency before resume.")
    parser.add_argument("--run-id")
    parser.add_argument("--run-dir")
    args = parser.parse_args()
    run = resolve_run_dir(args.run_id, args.run_dir)
    run_id = args.run_id or run.name
    report = check(run, run_id)
    write_json(run / "task-board-consistency.json", report)
    (run / "task-board-consistency.md").write_text(render_md(report), encoding="utf-8")
    print(json.dumps({"status": report["status"], "run_id": run_id, "path": str(run / "task-board-consistency.json"), "issues": report["issues"]}, indent=2))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
