#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from task_board_common import branch_state_map, child_counts, has_evidence, load_json, normalize_status, now, resolve_run_dir, write_json


ALLOWED_START_STATES = {"paused", "progress_snapshot", "redirected", "replanning", "resume_safety_check", "resume_blocked", "resume_ready"}
NON_EXECUTABLE = {"abandoned", "redo_needed", "paused"}


def newer(left: Path, right: Path) -> bool:
    return left.exists() and (not right.exists() or left.stat().st_mtime > right.stat().st_mtime)


def add(issues: list[dict], typ: str, severity: str = "blocker", **extra: object) -> None:
    issues.append({"severity": severity, "type": typ, **extra})


def check_obligations(run: Path, issues: list[dict]) -> None:
    data = load_json(run / "obligation-ledger.json", {})
    for item in data.get("implicit_obligations", []):
        if item.get("status") == "required" and not has_evidence(item):
            add(issues, "open_required_obligation", obligation_id=item.get("obligation_id", "unknown"), fix="close, defer, or escalate required obligation")


def check_quality_gate(run: Path, issues: list[dict]) -> None:
    gate = load_json(run / "quality-gate.json", {})
    if gate and gate.get("status") not in {"pass", "not_required"}:
        add(issues, "quality_gate_not_pass", status=gate.get("status"))


def check(run: Path, run_id: str) -> dict:
    issues: list[dict] = []
    warnings: list[dict] = []
    ledger = load_json(run / "run-ledger.json", {"run_id": run_id, "current_state": "unknown"})
    current_state = str(ledger.get("current_state", "unknown"))
    if current_state not in ALLOWED_START_STATES:
        add(issues, "invalid_resume_start_state", current_state=current_state, allowed=sorted(ALLOWED_START_STATES))
    if current_state in {"redirected", "replanning", "resume_safety_check"} and not (run / "redirect-plan.json").exists():
        add(issues, "missing_redirect_plan_for_resume", current_state=current_state)
    if newer(run / "TASKS.md", run / "task-board.json"):
        add(issues, "tasks_newer_than_task_board", fix="run apply-task-board.py before resume")
    if newer(run / "TASKS.md", run / "redirect-plan.json"):
        add(issues, "tasks_newer_than_redirect_plan", fix="run apply-task-board.py before resume")
    branch_state = load_json(run / "branch-state.json", {"branches": []})
    branches = branch_state.get("branches", [])
    state_by_id = branch_state_map(branch_state)
    status_by_id = {bid: normalize_status(item.get("status")) for bid, item in state_by_id.items()}
    children = child_counts(branches)
    queue = load_json(run / "merge-queue.json", {"queue": []})
    for item in queue.get("queue", []):
        bid = item.get("branch_id")
        status = status_by_id.get(bid)
        if status in NON_EXECUTABLE:
            add(issues, "merge_queue_references_non_executable_branch", branch_id=bid, branch_status=status, queue_status=item.get("status"), fix="update merge queue before resume")
        if item.get("status") in {"waiting_for_completion", "ready_for_serial_merge"} and item.get("review_status") in {"fail", "missing"}:
            add(issues, "merge_queue_item_missing_review", branch_id=bid)
        if item.get("status") in {"ready_for_serial_merge"} and item.get("parent_aggregation_status") not in {"pass", "not_required"}:
            add(issues, "merge_queue_item_missing_parent_aggregation", branch_id=bid)
    for bid, item in state_by_id.items():
        status = status_by_id.get(bid)
        if status == "retained" and not has_evidence(item):
            add(issues, "retained_branch_missing_evidence", branch_id=bid)
        if status == "done" and item.get("user_override") == "redo_needed":
            add(issues, "redo_needed_branch_still_done", branch_id=bid)
        if children.get(bid) and status in {"active", "planned"}:
            warnings.append({"severity": "warning", "type": "aggregation_node_executable_status", "branch_id": bid, "fix": "parent/root nodes should aggregate, not execute"})
    schedule = load_json(run / "branch-schedule.json", {"branches": []})
    for item in schedule.get("branches", []):
        bid = item.get("branch_id")
        # serial_branches can be a denial/reporting bucket; only concrete
        # execution modes should block parent/root aggregation nodes.
        if children.get(bid) and item.get("execution_mode") in {"parallel", "serial", "ready_for_serial_execution"}:
            add(issues, "root_or_parent_aggregation_node_in_execution_queue", branch_id=bid, execution_mode=item.get("execution_mode"))
    if queue.get("queue") and not (run / "parent-aggregation.json").exists():
        add(issues, "parent_aggregation_missing_but_merge_queue_non_empty", fix="run parent-aggregation-gate.py")
    resource_locks = load_json(run / "resource-locks.json", {})
    for resource in resource_locks.get("resources", []):
        if resource.get("status") == "unknown" and resource.get("lock_type") != "read_only":
            add(issues, "stale_or_unknown_resource_lock", resource_id=resource.get("resource_id"), severity="blocker")
    worktree_map = load_json(run / "worktree-map.json", {"branches": []})
    for item in worktree_map.get("branches", []):
        bid = item.get("branch_id")
        status = status_by_id.get(bid)
        if item.get("status") == "paused" and status == "active":
            add(issues, "paused_worktree_would_continue", branch_id=bid)
        path = str(item.get("worktree_path", ""))
        if path and not Path(path).exists():
            warnings.append({"severity": "warning", "type": "worktree_path_missing", "branch_id": bid, "worktree_path": path})
    check_obligations(run, issues)
    check_quality_gate(run, issues)
    status = "pass" if not issues else "fail"
    return {
        "schema_version": "1.1",
        "run_id": run_id,
        "goal_id": ledger.get("goal_id", "unknown"),
        "created_at": now(),
        "status": status,
        "resume_allowed": status == "pass",
        "issues": issues,
        "warnings": warnings,
        "minimal_fix_actions": sorted({x.get("fix", "review issue") for x in issues}),
    }


def render_md(report: dict) -> str:
    lines = ["# Resume Safety Check", "", f"- status: `{report['status']}`", f"- resume_allowed: `{report['resume_allowed']}`", ""]
    lines.extend(["## Issues", ""])
    lines.extend([f"- `{json.dumps(x, ensure_ascii=False)}`" for x in report["issues"]] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- `{json.dumps(x, ensure_ascii=False)}`" for x in report["warnings"]] or ["- none"])
    lines.extend(["", "## Minimal Fix Actions", ""])
    lines.extend([f"- {x}" for x in report["minimal_fix_actions"]] or ["- none"])
    return "\n".join(lines) + "\n"


def update_ledger(run: Path, report: dict) -> None:
    ledger = load_json(run / "run-ledger.json", {"run_id": report["run_id"], "transitions": []})
    previous = ledger.get("current_state", "unknown")
    new_state = "resume_ready" if report["status"] == "pass" else "resume_blocked"
    ledger["previous_state"] = previous
    ledger["current_state"] = new_state
    ledger["next_allowed_states"] = ["planned", "branch_scoped", "executing"] if new_state == "resume_ready" else ["needs_user_decision", "fallback", "aborted"]
    ledger.setdefault("transitions", []).append({
        "at": now(),
        "from": previous,
        "to": new_state,
        "run_id": report["run_id"],
        "goal_id": report.get("goal_id", "unknown"),
        "branch_id": "root",
        "created_by_mode": "agent-orchestrator",
        "owner_mode": "agent-orchestrator",
        "model": "GPT-5.5",
        "input_artifacts": ["TASKS.md", "task-board.json", "branch-state.json", "merge-queue.json", "resource-locks.json"],
        "output_artifacts": ["resume-safety-check.json", "resume-safety-check.md"],
        "gate_status": report["status"],
        "decision": "resume_safety_check",
    })
    ledger["updated_at"] = now()
    write_json(run / "run-ledger.json", ledger)


def main() -> int:
    parser = argparse.ArgumentParser(description="Block stale or unsafe resume after Stop/Progress/Redirect/Apply Task Board.")
    parser.add_argument("--run-id")
    parser.add_argument("--run-dir")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run = resolve_run_dir(args.run_id, args.run_dir)
    run_id = args.run_id or run.name
    report = check(run, run_id)
    write_json(run / "resume-safety-check.json", report)
    (run / "resume-safety-check.md").write_text(render_md(report), encoding="utf-8")
    if not args.dry_run:
        update_ledger(run, report)
    print(json.dumps({"status": report["status"], "run_id": run_id, "resume_allowed": report["resume_allowed"], "path": str(run / "resume-safety-check.json"), "issues": report["issues"]}, indent=2))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
