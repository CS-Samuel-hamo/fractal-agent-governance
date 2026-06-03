#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from task_board_common import (
    CONFIRM_REQUIRED_TRANSITIONS,
    DIRECT_ALLOWED_TRANSITIONS,
    branch_state_map,
    child_counts,
    has_evidence,
    load_json,
    normalize_status,
    now,
    parent_id,
    resolve_run_dir,
    task_board_map,
    write_json,
)


BAD_QUEUE_STATUSES = {"abandoned", "redo_needed", "paused"}


def ensure_proposed(run: Path, run_id: str) -> Path:
    proposed = run / "task-board.proposed.json"
    if proposed.exists():
        return proposed
    script = Path(__file__).with_name("parse-task-board.py")
    subprocess.run([sys.executable, str(script), "--run-id", run_id, "--run-dir", str(run)], check=True)
    return proposed


def mtime_warning(run: Path) -> list[dict]:
    warnings = []
    tasks = run / "TASKS.md"
    board = run / "task-board.json"
    redirect = run / "redirect-plan.json"
    branch_state = run / "branch-state.json"
    if tasks.exists() and board.exists() and tasks.stat().st_mtime > board.stat().st_mtime:
        warnings.append({"type": "tasks_newer_than_task_board", "required_action": "apply_task_board"})
    if tasks.exists() and redirect.exists() and tasks.stat().st_mtime > redirect.stat().st_mtime:
        warnings.append({"type": "tasks_newer_than_redirect_plan", "required_action": "apply_task_board"})
    if redirect.exists() and branch_state.exists() and redirect.stat().st_mtime > branch_state.stat().st_mtime:
        warnings.append({"type": "redirect_newer_than_branch_state", "required_action": "apply_redirect_plan_or_resume_safety_check"})
    return warnings


def branch_changes(proposed: dict, branch_state: dict, old_board: dict) -> tuple[list[dict], list[dict], list[dict]]:
    state_by_id = branch_state_map(branch_state)
    old_by_id = task_board_map(old_board)
    changes = []
    invalid = []
    decisions = []
    children = child_counts(proposed.get("tasks", []))
    for task in proposed.get("tasks", []):
        bid = task.get("branch_id")
        old_status = normalize_status(state_by_id.get(bid, {}).get("status") or old_by_id.get(bid, {}).get("status") or task.get("previous_status") or "planned")
        new_status = normalize_status(task.get("status"))
        if old_status == new_status:
            continue
        change = {
            "branch_id": bid,
            "from": old_status,
            "to": new_status,
            "title": task.get("title", bid),
            "risk_level": str(task.get("risk_level", "unknown")).lower(),
        }
        changes.append(change)
        if (old_status, new_status) in DIRECT_ALLOWED_TRANSITIONS:
            continue
        if (old_status, new_status) in CONFIRM_REQUIRED_TRANSITIONS:
            decisions.append({**change, "reason": "requires_gpt_or_user_confirmation"})
            continue
        invalid.append({**change, "reason": "invalid_or_unsafe_transition"})
        if children.get(bid) and new_status in {"active", "planned"}:
            decisions.append({**change, "reason": "parent_aggregation_node_cannot_be_forced_executable"})
        if change["risk_level"] in {"high", "critical"} and old_status != new_status:
            decisions.append({**change, "reason": "high_or_critical_risk_transition"})
    return changes, invalid, decisions


def queue_impact(proposed: dict, merge_queue: dict) -> tuple[list[dict], list[dict]]:
    status_by_id = {task.get("branch_id"): normalize_status(task.get("status")) for task in proposed.get("tasks", [])}
    affected = []
    invalid = []
    for item in merge_queue.get("queue", []):
        bid = item.get("branch_id")
        status = status_by_id.get(bid)
        if not status:
            continue
        if status in BAD_QUEUE_STATUSES:
            record = {"branch_id": bid, "branch_status": status, "queue_status": item.get("status"), "impact": "must_not_execute_or_merge"}
            affected.append(record)
            invalid.append({**record, "reason": "stale_merge_queue_references_non_executable_branch"})
        if status == "retained" and not has_evidence(item):
            affected.append({"branch_id": bid, "branch_status": status, "impact": "requires_evidence_before_parent_aggregation"})
    return affected, invalid


def resource_impact(proposed: dict, resource_locks: dict) -> list[dict]:
    if not resource_locks:
        return []
    status_by_id = {task.get("branch_id"): normalize_status(task.get("status")) for task in proposed.get("tasks", [])}
    impacts = []
    for resource in resource_locks.get("resources", []):
        owner = resource.get("owner_branch")
        if owner in status_by_id and status_by_id[owner] in BAD_QUEUE_STATUSES:
            impacts.append({
                "resource_id": resource.get("resource_id"),
                "type": resource.get("type"),
                "owner_branch": owner,
                "owner_status": status_by_id[owner],
                "impact": "resource_lock_requires_parent_review",
            })
    return impacts


def render_md(diff: dict) -> str:
    lines = ["# Task Board Diff", "", f"- status: `{diff['status']}`", f"- run_id: `{diff['run_id']}`", ""]
    for title, key in [
        ("Retained Branches", "retained_branches"),
        ("Abandoned Branches", "abandoned_branches"),
        ("Redo Needed Branches", "redo_needed_branches"),
        ("Paused Branches", "paused_branches"),
        ("Needs User Decision Branches", "needs_user_decision_branches"),
    ]:
        lines.extend([f"## {title}", ""])
        values = diff.get(key, [])
        lines.extend([f"- {x}" for x in values] or ["- none"])
        lines.append("")
    for title, key in [
        ("Invalid Transitions", "invalid_transitions"),
        ("Required User/GPT Decisions", "required_user_decisions"),
        ("Merge Queue Impact", "merge_queue_impact"),
        ("Resource Lock Impact", "resource_lock_impact"),
        ("Parent Aggregation Impact", "parent_aggregation_impact"),
        ("Stale Plan Warnings", "stale_plan_warnings"),
    ]:
        lines.extend([f"## {title}", ""])
        values = diff.get(key, [])
        lines.extend([f"- `{json.dumps(x, ensure_ascii=False)}`" for x in values] or ["- none"])
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diff task-board.proposed.json against runtime facts before applying changes.")
    parser.add_argument("--run-id")
    parser.add_argument("--run-dir")
    parser.add_argument("--proposed")
    args = parser.parse_args()
    run = resolve_run_dir(args.run_id, args.run_dir)
    run_id = args.run_id or run.name
    proposed_path = Path(args.proposed) if args.proposed else ensure_proposed(run, run_id)
    proposed = load_json(proposed_path, {"tasks": []})
    old_board = load_json(run / "task-board.json", {"tasks": []})
    branch_state = load_json(run / "branch-state.json", {"branches": []})
    worktree_map = load_json(run / "worktree-map.json", {"branches": []})
    merge_queue = load_json(run / "merge-queue.json", {"queue": []})
    resource_locks = load_json(run / "resource-locks.json", {})
    changes, invalid_transitions, required_decisions = branch_changes(proposed, branch_state, old_board)
    queue_affected, queue_invalid = queue_impact(proposed, merge_queue)
    resource_changes = resource_impact(proposed, resource_locks)
    parent_nodes = {parent_id(task) for task in proposed.get("tasks", []) if parent_id(task)}
    parent_impact = [
        {"branch_id": task.get("branch_id"), "impact": "aggregation_node_status_changed"}
        for task in proposed.get("tasks", [])
        if task.get("branch_id") in parent_nodes and any(c["branch_id"] == task.get("branch_id") for c in changes)
    ]
    status_groups = {name: [] for name in ["retained", "abandoned", "redo_needed", "paused", "needs_user_decision"]}
    for task in proposed.get("tasks", []):
        status = normalize_status(task.get("status"))
        if status in status_groups:
            status_groups[status].append(task.get("branch_id"))
    stale = mtime_warning(run)
    invalid_all = invalid_transitions
    diff = {
        "schema_version": "1.1",
        "run_id": run_id,
        "goal_id": proposed.get("goal_id", "unknown"),
        "created_at": now(),
        "status": "blocked" if invalid_all or required_decisions else "applicable",
        "changed_branches": changes,
        "retained_branches": sorted(status_groups["retained"]),
        "abandoned_branches": sorted(status_groups["abandoned"]),
        "redo_needed_branches": sorted(status_groups["redo_needed"]),
        "paused_branches": sorted(status_groups["paused"]),
        "needs_user_decision_branches": sorted(status_groups["needs_user_decision"]),
        "invalid_transitions": invalid_all,
        "required_user_decisions": required_decisions,
        "merge_queue_impact": queue_affected,
        "worktree_impact": [
            {"branch_id": item.get("branch_id"), "status": status_groups}
            for item in worktree_map.get("branches", [])
            if item.get("branch_id") in {c["branch_id"] for c in changes}
        ],
        "resource_lock_impact": resource_changes,
        "parent_aggregation_impact": parent_impact,
        "stale_plan_warnings": stale,
    }
    write_json(run / "task-board.diff.json", diff)
    (run / "task-board.diff.md").write_text(render_md(diff), encoding="utf-8")
    print(json.dumps({"status": diff["status"], "run_id": run_id, "diff_json": str(run / "task-board.diff.json"), "diff_md": str(run / "task-board.diff.md")}, indent=2))
    return 0 if diff["status"] == "applicable" else 2


if __name__ == "__main__":
    raise SystemExit(main())
